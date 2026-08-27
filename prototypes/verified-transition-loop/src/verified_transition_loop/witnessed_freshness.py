from __future__ import annotations

import base64
import binascii
import copy
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .canonical import (
    CANONICAL_PROFILE,
    MAX_SAFE_INTEGER,
    CanonicalizationError,
    canonical_bytes,
    canonical_sha256,
)

PROFILE_ID = "vtl-witnessed-freshness-v0.13"
SCHEMA_VERSION = "vtl.witnessed-freshness/v0.13"
STATEMENT_PROFILE_ID = "vtl-witness-statement/v0.13"
STATEMENT_SCHEMA_VERSION = "vtl.witness-statement/v0.13"
AUTHORITY_PROFILE_ID = "vtl-witness-authority/v0.13"
ED25519 = "ED25519"
PUBLIC_KEY_BYTES = 32
SIGNATURE_BYTES = 64

_VIEW_FIELDS = {"trust_root_id", "generation", "snapshot_digest"}
_AUTHORITY_FIELDS = {
    "profile_id",
    "quorum",
    "max_statement_age_ms",
    "allowed_algorithms",
    "keys",
}
_KEY_FIELDS = {
    "witness_id",
    "witness_key_id",
    "algorithm",
    "public_key_base64",
    "not_before_ms",
    "not_after_ms",
    "revoked",
}


@dataclass(frozen=True)
class WitnessedFreshnessResult:
    valid: bool
    local_snapshot_valid: bool
    witness_statement_integrity_valid: bool
    witness_signature_valid: bool
    witness_authority_valid: bool
    witness_freshness_valid: bool
    witness_quorum_valid: bool
    view_consistency_valid: bool
    equivocation_detected: bool
    accepted_witness_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]


def _invalid_result(
    local_snapshot_valid: Any, reasons: list[str]
) -> WitnessedFreshnessResult:
    return WitnessedFreshnessResult(
        valid=False,
        local_snapshot_valid=local_snapshot_valid is True,
        witness_statement_integrity_valid=False,
        witness_signature_valid=False,
        witness_authority_valid=False,
        witness_freshness_valid=False,
        witness_quorum_valid=False,
        view_consistency_valid=False,
        equivocation_detected=False,
        accepted_witness_ids=(),
        reason_codes=tuple(reasons),
    )


def _add(reasons: list[str], reason: str, condition: bool) -> None:
    if condition and reason not in reasons:
        reasons.append(reason)


def _string(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        canonical_bytes(value)
    except CanonicalizationError:
        return False
    return True


def _integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and abs(value) <= MAX_SAFE_INTEGER


def _positive_integer(value: Any) -> bool:
    return _integer(value) and value >= 1


def _timestamp(value: Any) -> bool:
    return _integer(value) and value >= 0


def _hex64(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdef" for ch in value)
    )


def _utf16_sort_key(value: str) -> bytes:
    return value.encode("utf-16-be")


def _decode_base64(value: Any) -> bytes | None:
    if not isinstance(value, str):
        return None
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return None
    if base64.b64encode(decoded).decode("ascii") != value:
        return None
    return decoded


_STATEMENT_FIELDS = (
    "profile_id",
    "schema_version",
    "canonical_profile",
    "trust_root_id",
    "generation",
    "snapshot_digest",
    "observed_at_ms",
    "witness_id",
    "witness_key_id",
    "signature_algorithm",
)
_STATEMENT_OBJECT_FIELDS = {
    *_STATEMENT_FIELDS,
    "statement_id",
    "signature",
}


def witness_statement(statement: Mapping[str, Any]) -> dict[str, Any]:
    return {field: statement.get(field) for field in _STATEMENT_FIELDS}


def compute_witness_statement_id(statement: Mapping[str, Any]) -> str:
    return "witness_" + canonical_sha256(witness_statement(statement))[:24]


def signed_witness_payload(statement: Mapping[str, Any]) -> bytes:
    return canonical_bytes(
        {
            "statement_id": statement.get("statement_id"),
            **witness_statement(statement),
        }
    )


def _validate_statement(statement: Any) -> tuple[str, ...]:
    if not isinstance(statement, Mapping):
        return ("WITNESS_STATEMENT_INVALID",)
    reasons: list[str] = []
    _add(
        reasons,
        "WITNESS_STATEMENT_FIELDS_INVALID",
        set(statement) != _STATEMENT_OBJECT_FIELDS,
    )
    required = {
        "statement_id": _string,
        "profile_id": _string,
        "schema_version": _string,
        "canonical_profile": _string,
        "trust_root_id": _string,
        "generation": _positive_integer,
        "snapshot_digest": _hex64,
        "observed_at_ms": _timestamp,
        "witness_id": _string,
        "witness_key_id": _string,
        "signature_algorithm": _string,
        "signature": lambda value: (
            (decoded := _decode_base64(value)) is not None
            and len(decoded) == SIGNATURE_BYTES
        ),
    }
    for field, predicate in required.items():
        if field not in statement or not predicate(statement[field]):
            _add(reasons, f"WITNESS_STATEMENT_SCHEMA_INVALID:{field}", True)
    return tuple(reasons)


def _validate_authority(authority: Any) -> tuple[str, ...]:
    if not isinstance(authority, Mapping):
        return ("WITNESS_AUTHORITY_INVALID",)
    reasons: list[str] = []
    _add(
        reasons,
        "WITNESS_AUTHORITY_FIELDS_INVALID",
        set(authority) != _AUTHORITY_FIELDS,
    )
    _add(
        reasons,
        "WITNESS_AUTHORITY_PROFILE_INVALID",
        authority.get("profile_id") != AUTHORITY_PROFILE_ID,
    )
    _add(
        reasons,
        "WITNESS_QUORUM_CONFIG_INVALID",
        not _positive_integer(authority.get("quorum")),
    )
    _add(
        reasons,
        "WITNESS_MAX_AGE_INVALID",
        not _positive_integer(authority.get("max_statement_age_ms")),
    )
    algorithms = authority.get("allowed_algorithms")
    _add(
        reasons,
        "WITNESS_ALLOWED_ALGORITHMS_INVALID",
        not isinstance(algorithms, list)
        or not algorithms
        or not all(_string(value) for value in algorithms)
        or len(set(algorithms)) != len(algorithms),
    )
    keys = authority.get("keys")
    if not isinstance(keys, list) or not keys:
        _add(reasons, "WITNESS_KEYS_INVALID", True)
        return tuple(reasons)
    for index, key in enumerate(keys):
        if not isinstance(key, Mapping):
            _add(reasons, f"WITNESS_KEY_INVALID:{index}", True)
            continue
        _add(
            reasons,
            f"WITNESS_KEY_FIELDS_INVALID:{index}",
            set(key) != _KEY_FIELDS,
        )
        specs = {
            "witness_id": _string,
            "witness_key_id": _string,
            "algorithm": _string,
            "public_key_base64": _string,
            "not_before_ms": _timestamp,
            "not_after_ms": _timestamp,
            "revoked": lambda value: isinstance(value, bool),
        }
        for field, predicate in specs.items():
            if field not in key or not predicate(key[field]):
                _add(reasons, f"WITNESS_KEY_SCHEMA_INVALID:{index}.{field}", True)
    return tuple(reasons)


def verify_witnessed_freshness(
    *,
    snapshot_view: Mapping[str, Any],
    local_snapshot_valid: bool,
    witness_statements: Sequence[Mapping[str, Any]],
    witness_authority: Mapping[str, Any],
    now_ms: int,
) -> WitnessedFreshnessResult:
    try:
        snapshot_view = copy.deepcopy(snapshot_view)
        witness_statements = copy.deepcopy(witness_statements)
        witness_authority = copy.deepcopy(witness_authority)
    except Exception:
        return _invalid_result(local_snapshot_valid, ["INPUT_SNAPSHOT_FAILED"])

    reasons: list[str] = []
    _add(reasons, "LOCAL_SNAPSHOT_INVALID", local_snapshot_valid is not True)
    _add(reasons, "NOW_MS_INVALID", not _timestamp(now_ms))
    view_valid = (
        isinstance(snapshot_view, Mapping)
        and set(snapshot_view) == _VIEW_FIELDS
        and _string(snapshot_view.get("trust_root_id"))
        and _positive_integer(snapshot_view.get("generation"))
        and _hex64(snapshot_view.get("snapshot_digest"))
    )
    _add(reasons, "SNAPSHOT_VIEW_INVALID", not view_valid)
    authority_reasons = list(_validate_authority(witness_authority))
    for reason in authority_reasons:
        _add(reasons, reason, True)
    statements_valid = (
        isinstance(witness_statements, Sequence)
        and not isinstance(witness_statements, (str, bytes))
        and bool(witness_statements)
    )
    if not statements_valid:
        _add(reasons, "WITNESS_STATEMENTS_INVALID", True)

    if not view_valid or authority_reasons or not _timestamp(now_ms) or not statements_valid:
        return _invalid_result(local_snapshot_valid, reasons)

    statement_integrity_valid = True
    all_signature_valid = True
    all_authority_valid = True
    all_fresh = True
    all_view_consistent = True
    equivocation_detected = False
    accepted: set[str] = set()
    seen_witness_ids: set[str] = set()

    keys = witness_authority["keys"]
    allowed_algorithms = witness_authority["allowed_algorithms"]
    max_age = witness_authority["max_statement_age_ms"]

    for statement in witness_statements:
        shape_reasons = list(_validate_statement(statement))
        for reason in shape_reasons:
            _add(reasons, reason, True)
        if shape_reasons:
            statement_integrity_valid = False
            all_signature_valid = False
            all_authority_valid = False
            all_fresh = False
            all_view_consistent = False
            continue

        integrity_ok = True
        profile_ok = (
            statement["profile_id"] == STATEMENT_PROFILE_ID
            and statement["schema_version"] == STATEMENT_SCHEMA_VERSION
        )
        canonical_ok = statement["canonical_profile"] == CANONICAL_PROFILE
        try:
            id_ok = statement["statement_id"] == compute_witness_statement_id(
                statement
            )
        except CanonicalizationError:
            id_ok = False
        _add(reasons, "WITNESS_PROFILE_MISMATCH", not profile_ok)
        _add(reasons, "WITNESS_CANONICAL_PROFILE_MISMATCH", not canonical_ok)
        _add(reasons, "WITNESS_STATEMENT_ID_INVALID", not id_ok)
        integrity_ok = profile_ok and canonical_ok and id_ok
        statement_integrity_valid = statement_integrity_valid and integrity_ok

        witness_id = statement["witness_id"]
        if witness_id in seen_witness_ids:
            _add(reasons, "DUPLICATE_WITNESS_ID", True)
            all_view_consistent = False
        seen_witness_ids.add(witness_id)

        matching = [
            key for key in keys
            if isinstance(key, Mapping)
            and key.get("witness_id") == witness_id
            and key.get("witness_key_id") == statement["witness_key_id"]
        ]
        _add(reasons, "WITNESS_NOT_TRUSTED", len(matching) == 0)
        _add(reasons, "WITNESS_KEY_AMBIGUOUS", len(matching) > 1)
        key = matching[0] if len(matching) == 1 else None

        signature_ok = False
        authority_ok = key is not None
        if key is not None:
            algorithm_ok = (
                statement["signature_algorithm"] == ED25519
                and key.get("algorithm") == ED25519
                and ED25519 in allowed_algorithms
            )
            _add(reasons, "WITNESS_ALGORITHM_NOT_ALLOWED", not algorithm_ok)
            key_interval_ok = (
                _timestamp(key.get("not_before_ms"))
                and _timestamp(key.get("not_after_ms"))
                and key["not_after_ms"] >= key["not_before_ms"]
            )
            _add(reasons, "WITNESS_KEY_VALIDITY_INVALID", not key_interval_ok)
            _add(reasons, "WITNESS_KEY_REVOKED", key.get("revoked") is True)
            key_current = key_interval_ok and key["not_before_ms"] <= now_ms <= key["not_after_ms"]
            _add(reasons, "WITNESS_KEY_NOT_CURRENT", key_interval_ok and not key_current)
            public_key = _decode_base64(key.get("public_key_base64"))
            signature = _decode_base64(statement["signature"])
            key_material_ok = public_key is not None and len(public_key) == PUBLIC_KEY_BYTES
            signature_material_ok = (
                signature is not None and len(signature) == SIGNATURE_BYTES
            )
            _add(reasons, "WITNESS_KEY_MATERIAL_INVALID", not key_material_ok)
            if algorithm_ok and key_material_ok and signature_material_ok:
                try:
                    Ed25519PublicKey.from_public_bytes(public_key).verify(
                        signature, signed_witness_payload(statement)
                    )
                    signature_ok = True
                except (CanonicalizationError, InvalidSignature, ValueError):
                    signature_ok = False
            _add(
                reasons,
                "WITNESS_SIGNATURE_INVALID",
                not signature_ok and algorithm_ok and key_material_ok,
            )
            authority_ok = (
                authority_ok
                and algorithm_ok
                and key_interval_ok
                and key_current
                and key.get("revoked") is False
                and key_material_ok
            )
        all_signature_valid = all_signature_valid and signature_ok
        all_authority_valid = all_authority_valid and authority_ok

        observed_at = statement["observed_at_ms"]
        from_future = observed_at > now_ms
        stale = not from_future and now_ms - observed_at > max_age
        _add(reasons, "WITNESS_STATEMENT_FROM_FUTURE", from_future)
        _add(reasons, "WITNESS_STATEMENT_STALE", stale)
        fresh_ok = not from_future and not stale
        all_fresh = all_fresh and fresh_ok

        root_match = statement["trust_root_id"] == snapshot_view["trust_root_id"]
        generation_match = statement["generation"] == snapshot_view["generation"]
        digest_match = statement["snapshot_digest"] == snapshot_view["snapshot_digest"]
        _add(reasons, "WITNESS_TRUST_ROOT_MISMATCH", not root_match)
        _add(reasons, "WITNESS_GENERATION_MISMATCH", not generation_match)
        _add(
            reasons,
            "WITNESS_SNAPSHOT_DIGEST_MISMATCH",
            root_match and generation_match and not digest_match,
        )
        exact_view = root_match and generation_match and digest_match
        if (
            integrity_ok
            and signature_ok
            and authority_ok
            and fresh_ok
            and root_match
            and generation_match
            and not digest_match
        ):
            equivocation_detected = True
            _add(reasons, "EQUIVOCATION_DETECTED", True)
        all_view_consistent = all_view_consistent and exact_view

        if integrity_ok and signature_ok and authority_ok and fresh_ok and exact_view:
            accepted.add(witness_id)

    quorum_valid = len(accepted) >= witness_authority["quorum"]
    _add(reasons, "WITNESS_QUORUM_NOT_MET", not quorum_valid)
    view_consistency_valid = all_view_consistent and not equivocation_detected
    valid = (
        local_snapshot_valid is True
        and statement_integrity_valid
        and all_signature_valid
        and all_authority_valid
        and all_fresh
        and quorum_valid
        and view_consistency_valid
        and not equivocation_detected
        and not reasons
    )
    return WitnessedFreshnessResult(
        valid=valid,
        local_snapshot_valid=local_snapshot_valid is True,
        witness_statement_integrity_valid=statement_integrity_valid,
        witness_signature_valid=all_signature_valid,
        witness_authority_valid=all_authority_valid,
        witness_freshness_valid=all_fresh,
        witness_quorum_valid=quorum_valid,
        view_consistency_valid=view_consistency_valid,
        equivocation_detected=equivocation_detected,
        accepted_witness_ids=tuple(sorted(accepted, key=_utf16_sort_key)),
        reason_codes=tuple(reasons),
    )
