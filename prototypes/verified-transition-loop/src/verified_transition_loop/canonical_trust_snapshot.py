from __future__ import annotations

import argparse
import base64
import binascii
import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .canonical import (
    CANONICAL_PROFILE,
    MAX_SAFE_INTEGER,
    CanonicalizationError,
    canonical_bytes,
    canonical_sha256,
    strict_loads,
)
from .canonical_signed_envelope import TRUST_ROOT_PROFILE_ID

PROFILE_ID = "vtl-canonical-trust-root-snapshot-v0.12"
SCHEMA_VERSION = "vtl.canonical-trust-root-snapshot/v0.12"
FIXTURE_SCHEMA_VERSION = "vtl.canonical-trust-root-snapshot-fixture/v0.12"
BOOTSTRAP_PROFILE_ID = "vtl-canonical-bootstrap-authority/v0.12"
CHECKPOINT_PROFILE_ID = "vtl-canonical-trust-checkpoint/v0.12"
ED25519 = "ED25519"
PUBLIC_KEY_BYTES = 32


@dataclass(frozen=True)
class CanonicalSnapshotResult:
    valid: bool
    snapshot_integrity_valid: bool
    canonical_profile_valid: bool
    bootstrap_signature_valid: bool
    bootstrap_authority_valid: bool
    freshness_valid: bool
    continuity_valid: bool
    signed_payload_base64: str
    snapshot_digest: str | None
    reason_codes: tuple[str, ...]


def _add(reasons: list[str], reason: str, condition: bool) -> None:
    if condition and reason not in reasons:
        reasons.append(reason)


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _integer(value: Any) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and abs(value) <= MAX_SAFE_INTEGER
    )


def _positive_integer(value: Any) -> bool:
    return _integer(value) and value >= 1


def _hex64(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdef" for ch in value)
    )


def _nullable_hex64(value: Any) -> bool:
    return value is None or _hex64(value)


def _decode_base64(value: str) -> bytes | None:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return None


_STATEMENT_FIELDS = (
    "profile_id",
    "schema_version",
    "canonical_profile",
    "trust_root_id",
    "policy_version",
    "generation",
    "previous_snapshot_digest",
    "trust_root_digest",
    "issued_at_ms",
    "not_before_ms",
    "not_after_ms",
    "issuer_id",
    "bootstrap_authority_id",
    "bootstrap_key_id",
    "signature_algorithm",
)


def snapshot_statement(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {field: snapshot.get(field) for field in _STATEMENT_FIELDS}


def compute_snapshot_id(snapshot: Mapping[str, Any]) -> str:
    return "snapshot_" + canonical_sha256(snapshot_statement(snapshot))[:24]


def signed_snapshot_payload(snapshot: Mapping[str, Any]) -> bytes:
    return canonical_bytes(
        {
            "snapshot_id": snapshot.get("snapshot_id"),
            **snapshot_statement(snapshot),
        }
    )


def trust_root_digest(trust_root: Mapping[str, Any]) -> str:
    return canonical_sha256(dict(trust_root))


def snapshot_digest(snapshot: Mapping[str, Any]) -> str:
    return canonical_sha256(dict(snapshot))


def _invalid_result(reasons: list[str]) -> CanonicalSnapshotResult:
    return CanonicalSnapshotResult(
        valid=False,
        snapshot_integrity_valid=False,
        canonical_profile_valid=False,
        bootstrap_signature_valid=False,
        bootstrap_authority_valid=False,
        freshness_valid=False,
        continuity_valid=False,
        signed_payload_base64="",
        snapshot_digest=None,
        reason_codes=tuple(reasons),
    )


def validate_snapshot_shape(snapshot: Any) -> tuple[str, ...]:
    if not isinstance(snapshot, Mapping):
        return ("SNAPSHOT_ROOT_INVALID",)
    reasons: list[str] = []
    required = {
        "snapshot_id": _non_empty_string,
        "profile_id": _non_empty_string,
        "schema_version": _non_empty_string,
        "canonical_profile": _non_empty_string,
        "trust_root_id": _non_empty_string,
        "policy_version": _non_empty_string,
        "generation": _positive_integer,
        "previous_snapshot_digest": _nullable_hex64,
        "trust_root_digest": _hex64,
        "issued_at_ms": _integer,
        "not_before_ms": _integer,
        "not_after_ms": _integer,
        "issuer_id": _non_empty_string,
        "bootstrap_authority_id": _non_empty_string,
        "bootstrap_key_id": _non_empty_string,
        "signature_algorithm": _non_empty_string,
        "signature": _non_empty_string,
    }
    for field, predicate in required.items():
        if field not in snapshot or not predicate(snapshot[field]):
            _add(reasons, f"SNAPSHOT_SCHEMA_INVALID:{field}", True)

    root = snapshot.get("trust_root")
    if not isinstance(root, Mapping):
        _add(reasons, "SNAPSHOT_SCHEMA_INVALID:trust_root", True)
    else:
        _add(
            reasons,
            "SNAPSHOT_TRUST_ROOT_PROFILE_INVALID",
            root.get("profile_id") != TRUST_ROOT_PROFILE_ID,
        )
        _add(
            reasons,
            "SNAPSHOT_TRUST_ROOT_ID_INVALID",
            not _non_empty_string(root.get("trust_root_id")),
        )
        _add(
            reasons,
            "SNAPSHOT_TRUST_POLICY_INVALID",
            not _non_empty_string(root.get("policy_version")),
        )
        algorithms = root.get("allowed_algorithms")
        _add(
            reasons,
            "SNAPSHOT_TRUST_ALGORITHMS_INVALID",
            not isinstance(algorithms, list)
            or not algorithms
            or not all(_non_empty_string(value) for value in algorithms),
        )
        keys = root.get("keys")
        _add(reasons, "SNAPSHOT_TRUST_KEYS_INVALID", not isinstance(keys, list))
    return tuple(reasons)


def validate_bootstrap_authority_shape(authority: Any) -> tuple[str, ...]:
    if not isinstance(authority, Mapping):
        return ("BOOTSTRAP_AUTHORITY_INVALID",)
    reasons: list[str] = []
    _add(
        reasons,
        "BOOTSTRAP_PROFILE_INVALID",
        authority.get("profile_id") != BOOTSTRAP_PROFILE_ID,
    )
    _add(
        reasons,
        "BOOTSTRAP_AUTHORITY_ID_INVALID",
        not _non_empty_string(authority.get("bootstrap_authority_id")),
    )
    algorithms = authority.get("allowed_algorithms")
    _add(
        reasons,
        "BOOTSTRAP_ALLOWED_ALGORITHMS_INVALID",
        not isinstance(algorithms, list)
        or not algorithms
        or not all(_non_empty_string(value) for value in algorithms),
    )
    keys = authority.get("keys")
    if not isinstance(keys, list) or not keys:
        _add(reasons, "BOOTSTRAP_KEYS_INVALID", True)
        return tuple(reasons)
    for index, key in enumerate(keys):
        if not isinstance(key, Mapping):
            _add(reasons, f"BOOTSTRAP_KEY_INVALID:{index}", True)
            continue
        specs = {
            "bootstrap_key_id": _non_empty_string,
            "issuer_id": _non_empty_string,
            "algorithm": _non_empty_string,
            "public_key_base64": _non_empty_string,
            "not_before_ms": _integer,
            "not_after_ms": _integer,
            "revoked": lambda value: isinstance(value, bool),
        }
        for field, predicate in specs.items():
            if field not in key or not predicate(key[field]):
                _add(reasons, f"BOOTSTRAP_KEY_SCHEMA_INVALID:{index}.{field}", True)
    return tuple(reasons)


def validate_checkpoint_shape(checkpoint: Any) -> tuple[str, ...]:
    if not isinstance(checkpoint, Mapping):
        return ("CHECKPOINT_INVALID",)
    reasons: list[str] = []
    _add(
        reasons,
        "CHECKPOINT_PROFILE_INVALID",
        checkpoint.get("profile_id") != CHECKPOINT_PROFILE_ID,
    )
    _add(
        reasons,
        "CHECKPOINT_TRUST_ROOT_ID_INVALID",
        not _non_empty_string(checkpoint.get("trust_root_id")),
    )
    _add(
        reasons,
        "CHECKPOINT_MINIMUM_GENERATION_INVALID",
        not _positive_integer(checkpoint.get("minimum_generation")),
    )
    _add(
        reasons,
        "CHECKPOINT_TIME_INVALID",
        not _integer(checkpoint.get("checkpointed_at_ms")),
    )
    known_generation = checkpoint.get("known_generation")
    known_digest = checkpoint.get("known_snapshot_digest")
    if (known_generation is None) != (known_digest is None):
        _add(reasons, "CHECKPOINT_KNOWN_STATE_INCOMPLETE", True)
    elif known_generation is not None:
        _add(
            reasons,
            "CHECKPOINT_KNOWN_GENERATION_INVALID",
            not _positive_integer(known_generation),
        )
        _add(reasons, "CHECKPOINT_KNOWN_DIGEST_INVALID", not _hex64(known_digest))
    return tuple(reasons)


def verify_canonical_trust_snapshot(
    snapshot: Any,
    bootstrap_authority: Any,
    checkpoint: Any,
    *,
    now_ms: int,
) -> CanonicalSnapshotResult:
    reasons = list(validate_snapshot_shape(snapshot))
    for reason in validate_bootstrap_authority_shape(bootstrap_authority):
        _add(reasons, reason, True)
    for reason in validate_checkpoint_shape(checkpoint):
        _add(reasons, reason, True)
    if not _integer(now_ms):
        _add(reasons, "NOW_MS_INVALID", True)
    if reasons:
        return _invalid_result(reasons)

    snapshot = dict(snapshot)
    root = dict(snapshot["trust_root"])
    bootstrap_authority = dict(bootstrap_authority)
    checkpoint = dict(checkpoint)

    try:
        current_snapshot_digest = snapshot_digest(snapshot)
        current_root_digest = trust_root_digest(root)
        expected_snapshot_id = compute_snapshot_id(snapshot)
        signed = signed_snapshot_payload(snapshot)
    except CanonicalizationError as exc:
        return _invalid_result([f"CANONICALIZATION_ERROR:{exc.code}"])

    signed_payload_base64 = base64.b64encode(signed).decode("ascii")
    canonical_profile_valid = snapshot["canonical_profile"] == CANONICAL_PROFILE

    integrity_reasons: list[str] = []
    _add(
        integrity_reasons,
        "CANONICAL_PROFILE_MISMATCH",
        not canonical_profile_valid,
    )
    _add(
        integrity_reasons,
        "TRUST_ROOT_DIGEST_MISMATCH",
        snapshot["trust_root_digest"] != current_root_digest,
    )
    _add(
        integrity_reasons,
        "TRUST_ROOT_ID_MISMATCH",
        snapshot["trust_root_id"] != root.get("trust_root_id"),
    )
    _add(
        integrity_reasons,
        "TRUST_POLICY_VERSION_MISMATCH",
        snapshot["policy_version"] != root.get("policy_version"),
    )
    _add(
        integrity_reasons,
        "SNAPSHOT_ID_INVALID",
        snapshot["snapshot_id"] != expected_snapshot_id,
    )
    for reason in integrity_reasons:
        _add(reasons, reason, True)
    snapshot_integrity_valid = not integrity_reasons

    authority_reasons: list[str] = []
    _add(
        authority_reasons,
        "BOOTSTRAP_AUTHORITY_MISMATCH",
        snapshot["bootstrap_authority_id"]
        != bootstrap_authority["bootstrap_authority_id"],
    )
    algorithm = snapshot["signature_algorithm"]
    algorithm_allowed = (
        algorithm == ED25519
        and algorithm in bootstrap_authority["allowed_algorithms"]
    )
    _add(
        authority_reasons,
        "BOOTSTRAP_ALGORITHM_NOT_ALLOWED",
        not algorithm_allowed,
    )
    matching_keys = [
        key
        for key in bootstrap_authority["keys"]
        if isinstance(key, Mapping)
        and key.get("bootstrap_key_id") == snapshot["bootstrap_key_id"]
    ]
    _add(
        authority_reasons,
        "BOOTSTRAP_KEY_NOT_TRUSTED",
        len(matching_keys) == 0,
    )
    _add(
        authority_reasons,
        "BOOTSTRAP_KEY_AMBIGUOUS",
        len(matching_keys) > 1,
    )
    key = matching_keys[0] if len(matching_keys) == 1 else None

    bootstrap_signature_valid = False
    if key is not None:
        _add(
            authority_reasons,
            "BOOTSTRAP_ISSUER_MISMATCH",
            key.get("issuer_id") != snapshot["issuer_id"],
        )
        _add(
            authority_reasons,
            "BOOTSTRAP_KEY_ALGORITHM_MISMATCH",
            key.get("algorithm") != algorithm,
        )
        _add(
            authority_reasons,
            "BOOTSTRAP_KEY_REVOKED",
            key.get("revoked") is True,
        )
        key_not_before = key.get("not_before_ms")
        key_not_after = key.get("not_after_ms")
        key_interval_valid = (
            _integer(key_not_before)
            and _integer(key_not_after)
            and key_not_after >= key_not_before
        )
        _add(
            authority_reasons,
            "BOOTSTRAP_KEY_VALIDITY_INVALID",
            not key_interval_valid,
        )
        _add(
            authority_reasons,
            "BOOTSTRAP_KEY_NOT_CURRENT",
            key_interval_valid
            and (now_ms < key_not_before or now_ms > key_not_after),
        )
        public_key_bytes = (
            _decode_base64(key.get("public_key_base64", ""))
            if _non_empty_string(key.get("public_key_base64"))
            else None
        )
        key_material_valid = (
            public_key_bytes is not None and len(public_key_bytes) == PUBLIC_KEY_BYTES
        )
        _add(
            authority_reasons,
            "BOOTSTRAP_KEY_MATERIAL_INVALID",
            not key_material_valid,
        )
        signature_bytes = _decode_base64(snapshot["signature"])
        if (
            algorithm_allowed
            and key.get("algorithm") == ED25519
            and key_material_valid
            and signature_bytes is not None
        ):
            try:
                Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(
                    signature_bytes,
                    signed,
                )
                bootstrap_signature_valid = True
            except (InvalidSignature, ValueError):
                bootstrap_signature_valid = False
        _add(
            reasons,
            "SNAPSHOT_SIGNATURE_INVALID",
            not bootstrap_signature_valid
            and algorithm_allowed
            and key_material_valid,
        )

    for reason in authority_reasons:
        _add(reasons, reason, True)
    bootstrap_authority_valid = not authority_reasons

    freshness_reasons: list[str] = []
    validity_interval_valid = snapshot["not_after_ms"] >= snapshot["not_before_ms"]
    _add(
        freshness_reasons,
        "SNAPSHOT_VALIDITY_INVALID",
        not validity_interval_valid,
    )
    _add(
        freshness_reasons,
        "SNAPSHOT_NOT_YET_VALID",
        validity_interval_valid and now_ms < snapshot["not_before_ms"],
    )
    _add(
        freshness_reasons,
        "SNAPSHOT_EXPIRED",
        validity_interval_valid and now_ms > snapshot["not_after_ms"],
    )
    _add(
        freshness_reasons,
        "SNAPSHOT_ISSUED_IN_FUTURE",
        snapshot["issued_at_ms"] > now_ms,
    )
    _add(
        freshness_reasons,
        "CHECKPOINT_FROM_FUTURE",
        checkpoint["checkpointed_at_ms"] > now_ms,
    )
    _add(
        freshness_reasons,
        "SNAPSHOT_GENERATION_BELOW_FLOOR",
        snapshot["generation"] < checkpoint["minimum_generation"],
    )
    for reason in freshness_reasons:
        _add(reasons, reason, True)
    freshness_valid = not freshness_reasons

    continuity_reasons: list[str] = []
    _add(
        continuity_reasons,
        "CHECKPOINT_TRUST_ROOT_MISMATCH",
        checkpoint["trust_root_id"] != snapshot["trust_root_id"],
    )
    known_generation = checkpoint.get("known_generation")
    known_digest = checkpoint.get("known_snapshot_digest")
    if known_generation is not None and known_digest is not None:
        if snapshot["generation"] < known_generation:
            _add(continuity_reasons, "SNAPSHOT_ROLLBACK", True)
        elif snapshot["generation"] == known_generation:
            _add(
                continuity_reasons,
                "SNAPSHOT_FORK_DETECTED",
                current_snapshot_digest != known_digest,
            )
        elif snapshot["generation"] == known_generation + 1:
            _add(
                continuity_reasons,
                "PREVIOUS_SNAPSHOT_DIGEST_MISMATCH",
                snapshot["previous_snapshot_digest"] != known_digest,
            )
        else:
            _add(continuity_reasons, "SNAPSHOT_CONTINUITY_GAP", True)
    for reason in continuity_reasons:
        _add(reasons, reason, True)
    continuity_valid = not continuity_reasons

    valid = (
        snapshot_integrity_valid
        and canonical_profile_valid
        and bootstrap_signature_valid
        and bootstrap_authority_valid
        and freshness_valid
        and continuity_valid
        and not reasons
    )
    return CanonicalSnapshotResult(
        valid=valid,
        snapshot_integrity_valid=snapshot_integrity_valid,
        canonical_profile_valid=canonical_profile_valid,
        bootstrap_signature_valid=bootstrap_signature_valid,
        bootstrap_authority_valid=bootstrap_authority_valid,
        freshness_valid=freshness_valid,
        continuity_valid=continuity_valid,
        signed_payload_base64=signed_payload_base64,
        snapshot_digest=current_snapshot_digest,
        reason_codes=tuple(reasons),
    )


def _set_path(document: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cursor: Any = document
    for part in parts[:-1]:
        cursor = cursor[int(part)] if isinstance(cursor, list) else cursor[part]
    last = parts[-1]
    if isinstance(cursor, list):
        cursor[int(last)] = copy.deepcopy(value)
    else:
        cursor[last] = copy.deepcopy(value)


def run_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for case in fixture["cases"]:
        snapshot = copy.deepcopy(fixture["snapshots"][case["snapshot_ref"]])
        authority = copy.deepcopy(fixture["bootstrap_authority"])
        checkpoint = copy.deepcopy(fixture["checkpoints"][case["checkpoint_ref"]])
        for mutation in case.get("snapshot_mutations", []):
            _set_path(snapshot, mutation["path"], mutation["value"])
        for mutation in case.get("bootstrap_mutations", []):
            _set_path(authority, mutation["path"], mutation["value"])
        for mutation in case.get("checkpoint_mutations", []):
            _set_path(checkpoint, mutation["path"], mutation["value"])

        result = verify_canonical_trust_snapshot(
            snapshot,
            authority,
            checkpoint,
            now_ms=fixture["base_now_ms"],
        )
        actual = {
            "valid": result.valid,
            "snapshot_integrity_valid": result.snapshot_integrity_valid,
            "canonical_profile_valid": result.canonical_profile_valid,
            "bootstrap_signature_valid": result.bootstrap_signature_valid,
            "bootstrap_authority_valid": result.bootstrap_authority_valid,
            "freshness_valid": result.freshness_valid,
            "continuity_valid": result.continuity_valid,
            "reason_codes": list(result.reason_codes),
        }
        results.append(
            {
                "id": case["id"],
                "actual": actual,
                "expected": case["expected"],
                "passed": actual == case["expected"],
            }
        )

    fresh = copy.deepcopy(fixture["snapshots"]["fresh"])
    base_result = verify_canonical_trust_snapshot(
        fresh,
        copy.deepcopy(fixture["bootstrap_authority"]),
        copy.deepcopy(fixture["checkpoints"]["base"]),
        now_ms=fixture["base_now_ms"],
    )
    parity = {
        "signed_payload_base64": base_result.signed_payload_base64,
        "signed_payload_matches_expected": (
            base_result.signed_payload_base64
            == fixture["expected_fresh_signed_payload_base64"]
        ),
        "signature_base64": fresh["signature"],
        "signature_matches_expected": (
            fresh["signature"] == fixture["expected_fresh_signature_base64"]
        ),
        "snapshot_digest": base_result.snapshot_digest,
        "snapshot_digest_matches_expected": (
            base_result.snapshot_digest == fixture["expected_fresh_snapshot_digest"]
        ),
    }
    passed = sum(1 for result in results if result["passed"])
    all_passed = (
        passed == len(results)
        and parity["signed_payload_matches_expected"]
        and parity["signature_matches_expected"]
        and parity["snapshot_digest_matches_expected"]
    )
    return {
        "profile_id": PROFILE_ID,
        "schema_version": FIXTURE_SCHEMA_VERSION,
        "canonical_profile": CANONICAL_PROFILE,
        "parity": parity,
        "cases": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "all_passed": all_passed,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify VTL v0.12 canonical trust-root snapshot vectors"
    )
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args(argv)

    fixture = strict_loads(args.fixture.read_text(encoding="utf-8"))
    result = run_fixture(fixture)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["summary"]["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
