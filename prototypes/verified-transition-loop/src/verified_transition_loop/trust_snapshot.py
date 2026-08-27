from __future__ import annotations

import argparse
import base64
import binascii
import copy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .attestation import AuthenticityResult, validate_trust_root_shape, verify_attested_dispatch

PROFILE_ID = "vtl-trust-root-snapshot-v0.9"
SCHEMA_VERSION = "vtl.trust-root-snapshot/v0.9"
FIXTURE_SCHEMA_VERSION = "vtl.trust-root-snapshot-fixture/v0.9"
BOOTSTRAP_PROFILE_ID = "vtl-bootstrap-authority/v0.9"
CHECKPOINT_PROFILE_ID = "vtl-trust-checkpoint/v0.9"
ED25519 = "ED25519"
ED25519_PUBLIC_KEY_BYTES = 32


def _reject_duplicate_json_members(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON member name: {key}")
        value[key] = item
    return value


def _reject_nonfinite_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def _load_json(path: str | Path) -> Any:
    return json.loads(
        Path(path).read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_json_members,
        parse_constant=_reject_nonfinite_json_constant,
    )


@dataclass(frozen=True)
class SnapshotVerificationResult:
    valid: bool
    snapshot_integrity_valid: bool
    bootstrap_signature_valid: bool
    bootstrap_authority_valid: bool
    freshness_valid: bool
    continuity_valid: bool
    snapshot_digest: str | None
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class LayeredTrustResult:
    valid: bool
    snapshot: SnapshotVerificationResult
    attested_dispatch: AuthenticityResult | None


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _stable_id(prefix: str, value: Any) -> str:
    return f"{prefix}_{_digest(value)[:24]}"


def trust_root_digest(trust_root: Mapping[str, Any]) -> str:
    return _digest(dict(trust_root))


def snapshot_digest(snapshot: Mapping[str, Any]) -> str:
    return _digest(dict(snapshot))


_STATEMENT_FIELDS = (
    "profile_id",
    "schema_version",
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
_SNAPSHOT_FIELDS = frozenset(
    ("snapshot_id", *_STATEMENT_FIELDS, "signature", "trust_root")
)
_BOOTSTRAP_AUTHORITY_FIELDS = frozenset(
    ("profile_id", "bootstrap_authority_id", "allowed_algorithms", "keys")
)
_BOOTSTRAP_KEY_FIELDS = frozenset(
    (
        "bootstrap_key_id",
        "issuer_id",
        "algorithm",
        "public_key_base64",
        "not_before_ms",
        "not_after_ms",
        "revoked",
    )
)
_CHECKPOINT_FIELDS = frozenset(
    (
        "profile_id",
        "trust_root_id",
        "minimum_generation",
        "known_generation",
        "known_snapshot_digest",
        "checkpointed_at_ms",
    )
)


def snapshot_statement(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {field: snapshot.get(field) for field in _STATEMENT_FIELDS}


def compute_snapshot_id(snapshot: Mapping[str, Any]) -> str:
    return _stable_id("snapshot", snapshot_statement(snapshot))


def signed_snapshot_payload(snapshot: Mapping[str, Any]) -> bytes:
    return _canonical_json(
        {
            "snapshot_id": snapshot.get("snapshot_id"),
            **snapshot_statement(snapshot),
        }
    )


def _add(reasons: list[str], reason: str, condition: bool) -> None:
    if condition and reason not in reasons:
        reasons.append(reason)


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _positive_integer(value: Any) -> bool:
    return _integer(value) and value >= 1


def _non_negative_integer(value: Any) -> bool:
    return _integer(value) and value >= 0


def _json_compatible(value: Any) -> bool:
    if value is None or isinstance(value, (bool, int, str)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, (list, tuple)):
        return all(_json_compatible(item) for item in value)
    if isinstance(value, Mapping):
        return all(
            isinstance(key, str) and _json_compatible(item)
            for key, item in value.items()
        )
    return False


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


def validate_snapshot_shape(snapshot: Any) -> tuple[str, ...]:
    if not isinstance(snapshot, Mapping):
        return ("SNAPSHOT_ROOT_INVALID",)
    if not _json_compatible(snapshot):
        return ("SNAPSHOT_CANONICALIZATION_INVALID",)
    reasons: list[str] = []
    _add(
        reasons,
        "SNAPSHOT_SCHEMA_INVALID:additionalProperties",
        bool(set(snapshot) - _SNAPSHOT_FIELDS),
    )
    required = {
        "snapshot_id": _non_empty_string,
        "profile_id": lambda value: value == PROFILE_ID,
        "schema_version": lambda value: value == SCHEMA_VERSION,
        "trust_root_id": _non_empty_string,
        "policy_version": _non_empty_string,
        "generation": _positive_integer,
        "previous_snapshot_digest": _nullable_hex64,
        "trust_root_digest": _hex64,
        "issued_at_ms": _non_negative_integer,
        "not_before_ms": _non_negative_integer,
        "not_after_ms": _non_negative_integer,
        "issuer_id": _non_empty_string,
        "bootstrap_authority_id": _non_empty_string,
        "bootstrap_key_id": _non_empty_string,
        "signature_algorithm": _non_empty_string,
        "signature": _non_empty_string,
    }
    for field, predicate in required.items():
        if field not in snapshot or not predicate(snapshot[field]):
            _add(reasons, f"SNAPSHOT_SCHEMA_INVALID:{field}", True)
    trust_root = snapshot.get("trust_root")
    if not isinstance(trust_root, Mapping):
        _add(reasons, "SNAPSHOT_SCHEMA_INVALID:trust_root", True)
    elif validate_trust_root_shape(trust_root):
        _add(reasons, "SNAPSHOT_TRUST_ROOT_SHAPE_INVALID", True)
    return tuple(reasons)


def validate_bootstrap_authority_shape(authority: Any) -> tuple[str, ...]:
    if not isinstance(authority, Mapping):
        return ("BOOTSTRAP_AUTHORITY_INVALID",)
    if not _json_compatible(authority):
        return ("BOOTSTRAP_AUTHORITY_CANONICALIZATION_INVALID",)
    reasons: list[str] = []
    _add(
        reasons,
        "BOOTSTRAP_AUTHORITY_SCHEMA_INVALID:additionalProperties",
        bool(set(authority) - _BOOTSTRAP_AUTHORITY_FIELDS),
    )
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
        or not all(_non_empty_string(item) for item in algorithms),
    )
    keys = authority.get("keys")
    if not isinstance(keys, list) or not keys:
        _add(reasons, "BOOTSTRAP_KEYS_INVALID", True)
        return tuple(reasons)
    for index, key in enumerate(keys):
        if not isinstance(key, Mapping):
            _add(reasons, f"BOOTSTRAP_KEY_INVALID:{index}", True)
            continue
        _add(
            reasons,
            f"BOOTSTRAP_KEY_SCHEMA_INVALID:{index}.additionalProperties",
            bool(set(key) - _BOOTSTRAP_KEY_FIELDS),
        )
        specs = {
            "bootstrap_key_id": _non_empty_string,
            "issuer_id": _non_empty_string,
            "algorithm": _non_empty_string,
            "public_key_base64": _non_empty_string,
            "not_before_ms": _non_negative_integer,
            "not_after_ms": _non_negative_integer,
            "revoked": lambda value: isinstance(value, bool),
        }
        for field, predicate in specs.items():
            if field not in key or not predicate(key[field]):
                _add(reasons, f"BOOTSTRAP_KEY_SCHEMA_INVALID:{index}.{field}", True)
    return tuple(reasons)


def validate_checkpoint_shape(checkpoint: Any) -> tuple[str, ...]:
    if not isinstance(checkpoint, Mapping):
        return ("CHECKPOINT_INVALID",)
    if not _json_compatible(checkpoint):
        return ("CHECKPOINT_CANONICALIZATION_INVALID",)
    reasons: list[str] = []
    _add(
        reasons,
        "CHECKPOINT_SCHEMA_INVALID:additionalProperties",
        bool(set(checkpoint) - _CHECKPOINT_FIELDS),
    )
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
        not _non_negative_integer(checkpoint.get("checkpointed_at_ms")),
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
        _add(
            reasons,
            "CHECKPOINT_KNOWN_DIGEST_INVALID",
            not _hex64(known_digest),
        )
    return tuple(reasons)


def verify_trust_root_snapshot(
    snapshot: Any,
    bootstrap_authority: Any,
    checkpoint: Any,
    *,
    now_ms: int,
) -> SnapshotVerificationResult:
    reasons = list(validate_snapshot_shape(snapshot))
    _add(
        reasons,
        "VERIFICATION_TIME_INVALID",
        not _non_negative_integer(now_ms),
    )
    for reason in validate_bootstrap_authority_shape(bootstrap_authority):
        _add(reasons, reason, True)
    for reason in validate_checkpoint_shape(checkpoint):
        _add(reasons, reason, True)
    if reasons:
        return SnapshotVerificationResult(
            valid=False,
            snapshot_integrity_valid=False,
            bootstrap_signature_valid=False,
            bootstrap_authority_valid=False,
            freshness_valid=False,
            continuity_valid=False,
            snapshot_digest=None,
            reason_codes=tuple(reasons),
        )

    snapshot = dict(snapshot)
    root = dict(snapshot["trust_root"])
    bootstrap_authority = dict(bootstrap_authority)
    checkpoint = dict(checkpoint)
    current_snapshot_digest = snapshot_digest(snapshot)

    integrity_reasons: list[str] = []
    _add(
        integrity_reasons,
        "TRUST_ROOT_DIGEST_MISMATCH",
        snapshot["trust_root_digest"] != trust_root_digest(root),
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
        snapshot["snapshot_id"] != compute_snapshot_id(snapshot),
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
        if key["bootstrap_key_id"] == snapshot["bootstrap_key_id"]
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
            key["issuer_id"] != snapshot["issuer_id"],
        )
        _add(
            authority_reasons,
            "BOOTSTRAP_KEY_ALGORITHM_MISMATCH",
            key["algorithm"] != algorithm,
        )
        _add(
            authority_reasons,
            "BOOTSTRAP_KEY_REVOKED",
            key["revoked"] is True,
        )
        key_interval_valid = key["not_after_ms"] >= key["not_before_ms"]
        _add(
            authority_reasons,
            "BOOTSTRAP_KEY_VALIDITY_INVALID",
            not key_interval_valid,
        )
        _add(
            authority_reasons,
            "BOOTSTRAP_KEY_NOT_CURRENT",
            key_interval_valid
            and (now_ms < key["not_before_ms"] or now_ms > key["not_after_ms"]),
        )
        public_key_bytes = _decode_base64(key["public_key_base64"])
        key_material_valid = (
            public_key_bytes is not None
            and len(public_key_bytes) == ED25519_PUBLIC_KEY_BYTES
        )
        _add(
            authority_reasons,
            "BOOTSTRAP_KEY_MATERIAL_INVALID",
            not key_material_valid,
        )
        signature_bytes = _decode_base64(snapshot["signature"])
        if (
            algorithm_allowed
            and key["algorithm"] == ED25519
            and key_material_valid
            and signature_bytes is not None
        ):
            try:
                Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(
                    signature_bytes,
                    signed_snapshot_payload(snapshot),
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
        and bootstrap_signature_valid
        and bootstrap_authority_valid
        and freshness_valid
        and continuity_valid
        and not reasons
    )
    return SnapshotVerificationResult(
        valid=valid,
        snapshot_integrity_valid=snapshot_integrity_valid,
        bootstrap_signature_valid=bootstrap_signature_valid,
        bootstrap_authority_valid=bootstrap_authority_valid,
        freshness_valid=freshness_valid,
        continuity_valid=continuity_valid,
        snapshot_digest=current_snapshot_digest,
        reason_codes=tuple(reasons),
    )


def verify_attested_dispatch_with_snapshot(
    snapshot: Any,
    bootstrap_authority: Any,
    checkpoint: Any,
    attested_envelope: Any,
    *,
    now_ms: int,
) -> LayeredTrustResult:
    snapshot_result = verify_trust_root_snapshot(
        snapshot,
        bootstrap_authority,
        checkpoint,
        now_ms=now_ms,
    )
    if not snapshot_result.valid:
        return LayeredTrustResult(
            valid=False,
            snapshot=snapshot_result,
            attested_dispatch=None,
        )
    attested_result = verify_attested_dispatch(
        attested_envelope,
        snapshot["trust_root"],
        now_ms=now_ms,
    )
    return LayeredTrustResult(
        valid=attested_result.valid,
        snapshot=snapshot_result,
        attested_dispatch=attested_result,
    )


def _set_path(document: Any, path: str, value: Any) -> None:
    parts = path.split(".")
    cursor = document
    for part in parts[:-1]:
        if isinstance(cursor, list) and part.isdigit():
            index = int(part)
            if index >= len(cursor):
                raise ValueError(f"mutation path not found: {path}")
            cursor = cursor[index]
        elif isinstance(cursor, dict) and part in cursor:
            cursor = cursor[part]
        else:
            raise ValueError(f"mutation path not found: {path}")
    final = parts[-1]
    if isinstance(cursor, list) and final.isdigit():
        index = int(final)
        if index >= len(cursor):
            raise ValueError(f"mutation path not found: {path}")
        cursor[index] = copy.deepcopy(value)
    elif isinstance(cursor, dict) and final in cursor:
        cursor[final] = copy.deepcopy(value)
    else:
        raise ValueError(f"mutation path not found: {path}")


def validate_fixture_shape(fixture: Any) -> None:
    if not isinstance(fixture, Mapping):
        raise ValueError("fixture root must be an object")
    if fixture.get("profile_id") != PROFILE_ID:
        raise ValueError("fixture profile_id mismatch")
    if fixture.get("schema_version") != FIXTURE_SCHEMA_VERSION:
        raise ValueError("fixture schema_version mismatch")
    if validate_snapshot_shape(fixture.get("base_snapshot")):
        raise ValueError("fixture base_snapshot invalid")
    if validate_bootstrap_authority_shape(fixture.get("bootstrap_authority")):
        raise ValueError("fixture bootstrap_authority invalid")
    if validate_checkpoint_shape(fixture.get("base_checkpoint")):
        raise ValueError("fixture base_checkpoint invalid")
    cases = fixture.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("fixture cases must be a non-empty list")
    for case in cases:
        if not isinstance(case, Mapping) or not _non_empty_string(case.get("id")):
            raise ValueError("fixture case id missing")
        if not _non_negative_integer(case.get("now_ms")):
            raise ValueError(f"fixture case {case.get('id')} now_ms invalid")
        for bucket in (
            "snapshot_mutations",
            "bootstrap_authority_mutations",
            "checkpoint_mutations",
        ):
            mutations = case.get(bucket, [])
            if not isinstance(mutations, list):
                raise ValueError(f"fixture case {case['id']} {bucket} invalid")
            for mutation in mutations:
                if (
                    not isinstance(mutation, Mapping)
                    or not _non_empty_string(mutation.get("path"))
                    or "value" not in mutation
                ):
                    raise ValueError(f"fixture case {case['id']} mutation invalid")
        expected = case.get("expected")
        if not isinstance(expected, Mapping) or not isinstance(expected.get("valid"), bool):
            raise ValueError(f"fixture case {case['id']} expected invalid")
        reason_codes = expected.get("reason_codes")
        if not isinstance(reason_codes, list) or not all(
            isinstance(reason, str) for reason in reason_codes
        ):
            raise ValueError(f"fixture case {case['id']} reason_codes invalid")


def load_fixture(path: str | Path) -> dict[str, Any]:
    fixture = _load_json(path)
    validate_fixture_shape(fixture)
    return fixture


def run_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    validate_fixture_shape(fixture)
    results: list[dict[str, Any]] = []
    for case in fixture["cases"]:
        snapshot = copy.deepcopy(fixture["base_snapshot"])
        bootstrap_authority = copy.deepcopy(fixture["bootstrap_authority"])
        checkpoint = copy.deepcopy(fixture["base_checkpoint"])
        for mutation in case.get("snapshot_mutations", []):
            _set_path(snapshot, mutation["path"], mutation["value"])
        for mutation in case.get("bootstrap_authority_mutations", []):
            _set_path(
                bootstrap_authority,
                mutation["path"],
                mutation["value"],
            )
        for mutation in case.get("checkpoint_mutations", []):
            _set_path(checkpoint, mutation["path"], mutation["value"])
        result = verify_trust_root_snapshot(
            snapshot,
            bootstrap_authority,
            checkpoint,
            now_ms=case["now_ms"],
        )
        expected = case["expected"]
        expected_reasons = tuple(expected["reason_codes"])
        passed = (
            result.valid is expected["valid"]
            and result.reason_codes == expected_reasons
        )
        results.append(
            {
                "id": case["id"],
                "passed": passed,
                "actual": {
                    "valid": result.valid,
                    "snapshot_integrity_valid": result.snapshot_integrity_valid,
                    "bootstrap_signature_valid": result.bootstrap_signature_valid,
                    "bootstrap_authority_valid": result.bootstrap_authority_valid,
                    "freshness_valid": result.freshness_valid,
                    "continuity_valid": result.continuity_valid,
                    "reason_codes": list(result.reason_codes),
                },
                "expected": {
                    "valid": expected["valid"],
                    "reason_codes": list(expected_reasons),
                },
            }
        )
    passed_count = sum(item["passed"] for item in results)
    return {
        "profile_id": PROFILE_ID,
        "schema_version": FIXTURE_SCHEMA_VERSION,
        "cases": results,
        "summary": {
            "total": len(results),
            "passed": passed_count,
            "failed": len(results) - passed_count,
            "all_passed": passed_count == len(results),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify a VTL v0.9 trust-root snapshot against external bootstrap authority and checkpoint."
    )
    parser.add_argument("path", help="Trust-root snapshot or v0.9 fixture JSON")
    parser.add_argument("--bootstrap-authority", help="Verifier-controlled bootstrap authority JSON")
    parser.add_argument("--checkpoint", help="Verifier-controlled freshness checkpoint JSON")
    parser.add_argument("--now-ms", type=int, help="Verification time in epoch milliseconds")
    args = parser.parse_args(argv)

    data = _load_json(args.path)
    if isinstance(data, Mapping) and data.get("schema_version") == FIXTURE_SCHEMA_VERSION:
        result = run_fixture(data)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["summary"]["all_passed"] else 1

    if args.bootstrap_authority is None or args.checkpoint is None or args.now_ms is None:
        parser.error(
            "--bootstrap-authority, --checkpoint and --now-ms are required for a single snapshot"
        )
    bootstrap_authority = _load_json(args.bootstrap_authority)
    checkpoint = _load_json(args.checkpoint)
    result = verify_trust_root_snapshot(
        data,
        bootstrap_authority,
        checkpoint,
        now_ms=args.now_ms,
    )
    print(
        json.dumps(
            {
                "profile_id": PROFILE_ID,
                "schema_version": SCHEMA_VERSION,
                "valid": result.valid,
                "snapshot_integrity_valid": result.snapshot_integrity_valid,
                "bootstrap_signature_valid": result.bootstrap_signature_valid,
                "bootstrap_authority_valid": result.bootstrap_authority_valid,
                "freshness_valid": result.freshness_valid,
                "continuity_valid": result.continuity_valid,
                "snapshot_digest": result.snapshot_digest,
                "reason_codes": list(result.reason_codes),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
