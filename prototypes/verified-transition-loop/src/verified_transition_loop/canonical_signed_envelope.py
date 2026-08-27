from __future__ import annotations

import argparse
import base64
import binascii
import copy
import json
import re
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

PROFILE_ID = "vtl-canonical-signed-envelope-v0.11"
SCHEMA_VERSION = "vtl.canonical-signed-envelope/v0.11"
FIXTURE_SCHEMA_VERSION = "vtl.canonical-signed-envelope-fixture/v0.11"
TRUST_ROOT_PROFILE_ID = "vtl-canonical-trust-root/v0.11"
ED25519 = "ED25519"
PUBLIC_KEY_BYTES = 32
SIGNATURE_BYTES = 64

_ENVELOPE_FIELDS = {
    "profile_id",
    "schema_version",
    "canonical_profile",
    "payload",
    "attestation",
}
_ATTESTATION_FIELDS = {
    "attestation_id",
    "payload_digest",
    "issuer_id",
    "signer_key_id",
    "trust_root_id",
    "issued_at_ms",
    "not_before_ms",
    "not_after_ms",
    "signature_algorithm",
    "signature",
}
_TRUST_ROOT_FIELDS = {"profile_id", "trust_root_id", "allowed_algorithms", "keys"}
_TRUST_KEY_FIELDS = {
    "signer_key_id",
    "issuer_id",
    "algorithm",
    "public_key_base64",
    "not_before_ms",
    "not_after_ms",
    "revoked",
}
_FIXTURE_FIELDS = {
    "profile_id",
    "schema_version",
    "canonical_profile",
    "base_now_ms",
    "base_envelope",
    "trust_root",
    "expected_signed_payload_base64",
    "expected_signature_base64",
    "cases",
}
_CASE_FIELDS = {
    "id",
    "now_ms",
    "envelope_mutations",
    "trust_root_mutations",
    "expected",
}
_EXPECTED_FIELDS = {
    "valid",
    "payload_digest_matches",
    "attestation_id_valid",
    "canonical_profile_valid",
    "signature_valid",
    "trusted_current_authority",
    "reason_codes",
}
_MUTATION_FIELDS = {"path", "value"}
_DANGEROUS_PATH_PARTS = {"__proto__", "prototype", "constructor"}


@dataclass(frozen=True)
class CanonicalEnvelopeResult:
    valid: bool
    payload_digest_matches: bool
    attestation_id_valid: bool
    canonical_profile_valid: bool
    signature_valid: bool
    trusted_current_authority: bool
    signed_payload_base64: str
    reason_codes: tuple[str, ...]


def _add(reasons: list[str], reason: str, condition: bool) -> None:
    if condition and reason not in reasons:
        reasons.append(reason)


def _hex64(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdef" for ch in value)
    )


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _integer(value: Any) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and abs(value) <= MAX_SAFE_INTEGER
    )


def _timestamp(value: Any) -> bool:
    return _integer(value) and value >= 0


def _decode_base64(value: str) -> bytes | None:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return None
    return decoded if base64.b64encode(decoded).decode("ascii") == value else None


def _exact_dict(value: Any, fields: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == fields


def _invalid_result(code: str) -> CanonicalEnvelopeResult:
    return CanonicalEnvelopeResult(
        False, False, False, False, False, False, "", (code,)
    )


def _canonical_base64(value: Any, *, length: int | None = None) -> bool:
    if not _non_empty_string(value):
        return False
    decoded = _decode_base64(value)
    return decoded is not None and (length is None or len(decoded) == length)


def _trust_key_shape_valid(key: Any) -> bool:
    return (
        _exact_dict(key, _TRUST_KEY_FIELDS)
        and _non_empty_string(key["signer_key_id"])
        and _non_empty_string(key["issuer_id"])
        and _non_empty_string(key["algorithm"])
        and _non_empty_string(key["public_key_base64"])
        and _timestamp(key["not_before_ms"])
        and _timestamp(key["not_after_ms"])
        and isinstance(key["revoked"], bool)
    )


_STATEMENT_FIELDS = (
    "payload_digest",
    "issuer_id",
    "signer_key_id",
    "trust_root_id",
    "issued_at_ms",
    "not_before_ms",
    "not_after_ms",
    "signature_algorithm",
)


def attestation_statement(envelope: Mapping[str, Any]) -> dict[str, Any]:
    attestation = envelope["attestation"]
    return {
        "profile_id": envelope.get("profile_id"),
        "schema_version": envelope.get("schema_version"),
        "canonical_profile": envelope.get("canonical_profile"),
        **{field: attestation.get(field) for field in _STATEMENT_FIELDS},
    }


def compute_attestation_id(envelope: Mapping[str, Any]) -> str:
    return "attest_" + canonical_sha256(attestation_statement(envelope))[:24]


def signed_payload(envelope: Mapping[str, Any]) -> bytes:
    return canonical_bytes(
        {
            "attestation_id": envelope["attestation"].get("attestation_id"),
            **attestation_statement(envelope),
        }
    )


def verify_canonical_signed_envelope(
    envelope: Any,
    trust_root: Any,
    *,
    now_ms: int,
) -> CanonicalEnvelopeResult:
    reasons: list[str] = []

    if not isinstance(envelope, Mapping):
        return _invalid_result("ENVELOPE_ROOT_INVALID")
    if not isinstance(trust_root, Mapping):
        return _invalid_result("TRUST_ROOT_INVALID")
    if not _timestamp(now_ms):
        return _invalid_result("VERIFIER_TIME_INVALID")

    try:
        envelope = copy.deepcopy(dict(envelope))
        trust_root = copy.deepcopy(dict(trust_root))
    except (TypeError, ValueError, copy.Error):
        return _invalid_result("INPUT_SNAPSHOT_INVALID")

    _add(
        reasons,
        "ENVELOPE_SCHEMA_INVALID",
        not _exact_dict(envelope, _ENVELOPE_FIELDS),
    )

    _add(reasons, "PROFILE_ID_MISMATCH", envelope.get("profile_id") != PROFILE_ID)
    _add(
        reasons,
        "SCHEMA_VERSION_MISMATCH",
        envelope.get("schema_version") != SCHEMA_VERSION,
    )
    canonical_profile_valid = envelope.get("canonical_profile") == CANONICAL_PROFILE
    _add(reasons, "CANONICAL_PROFILE_MISMATCH", not canonical_profile_valid)

    payload = envelope.get("payload")
    attestation = envelope.get("attestation")
    if not isinstance(payload, (dict, list)):
        _add(reasons, "PAYLOAD_INVALID", True)
    if not isinstance(attestation, Mapping):
        _add(reasons, "ATTESTATION_INVALID", True)
        return CanonicalEnvelopeResult(
            False,
            False,
            False,
            canonical_profile_valid,
            False,
            False,
            "",
            tuple(reasons),
        )

    _add(
        reasons,
        "ATTESTATION_SCHEMA_INVALID:fields",
        not _exact_dict(attestation, _ATTESTATION_FIELDS),
    )

    required = {
        "attestation_id": _non_empty_string,
        "payload_digest": _hex64,
        "issuer_id": _non_empty_string,
        "signer_key_id": _non_empty_string,
        "trust_root_id": _non_empty_string,
        "issued_at_ms": _timestamp,
        "not_before_ms": _timestamp,
        "not_after_ms": _timestamp,
        "signature_algorithm": _non_empty_string,
        "signature": _non_empty_string,
    }
    required_value_invalid = False
    for field, predicate in required.items():
        if field not in attestation or not predicate(attestation[field]):
            required_value_invalid = True
            _add(reasons, f"ATTESTATION_SCHEMA_INVALID:{field}", True)

    if required_value_invalid or "PAYLOAD_INVALID" in reasons:
        return CanonicalEnvelopeResult(
            False,
            False,
            False,
            canonical_profile_valid,
            False,
            False,
            "",
            tuple(reasons),
        )

    try:
        actual_payload_digest = canonical_sha256(payload)
        signed = signed_payload(envelope)
    except CanonicalizationError as exc:
        _add(reasons, f"CANONICALIZATION_ERROR:{exc.code}", True)
        return CanonicalEnvelopeResult(
            False,
            False,
            False,
            canonical_profile_valid,
            False,
            False,
            "",
            tuple(reasons),
        )

    signed_payload_base64 = base64.b64encode(signed).decode("ascii")
    payload_digest_matches = attestation["payload_digest"] == actual_payload_digest
    _add(reasons, "PAYLOAD_DIGEST_MISMATCH", not payload_digest_matches)

    attestation_id_valid = (
        attestation["attestation_id"] == compute_attestation_id(envelope)
    )
    _add(reasons, "ATTESTATION_ID_INVALID", not attestation_id_valid)

    trust_reasons: list[str] = []
    _add(
        trust_reasons,
        "TRUST_ROOT_SCHEMA_INVALID",
        not _exact_dict(trust_root, _TRUST_ROOT_FIELDS)
        or not _non_empty_string(trust_root.get("trust_root_id")),
    )
    _add(
        trust_reasons,
        "TRUST_ROOT_PROFILE_INVALID",
        trust_root.get("profile_id") != TRUST_ROOT_PROFILE_ID,
    )
    _add(
        trust_reasons,
        "TRUST_ROOT_MISMATCH",
        attestation["trust_root_id"] != trust_root.get("trust_root_id"),
    )

    allowed_algorithms = trust_root.get("allowed_algorithms")
    if (
        not isinstance(allowed_algorithms, list)
        or not allowed_algorithms
        or not all(_non_empty_string(value) for value in allowed_algorithms)
        or len(set(allowed_algorithms)) != len(allowed_algorithms)
    ):
        _add(trust_reasons, "TRUST_ROOT_ALGORITHMS_INVALID", True)
        allowed_algorithms = []

    algorithm = attestation["signature_algorithm"]
    algorithm_allowed = algorithm == ED25519 and algorithm in allowed_algorithms
    _add(trust_reasons, "ALGORITHM_NOT_ALLOWED", not algorithm_allowed)

    keys = trust_root.get("keys")
    if (
        not isinstance(keys, list)
        or not keys
        or not all(_trust_key_shape_valid(key) for key in keys)
    ):
        _add(trust_reasons, "TRUST_ROOT_KEYS_INVALID", True)
    if not isinstance(keys, list):
        keys = []
    matching_keys = [
        key
        for key in keys
        if isinstance(key, Mapping)
        and key.get("signer_key_id") == attestation["signer_key_id"]
    ]
    key = matching_keys[0] if len(matching_keys) == 1 else None
    _add(trust_reasons, "SIGNER_NOT_TRUSTED", len(matching_keys) == 0)
    _add(trust_reasons, "SIGNER_KEY_AMBIGUOUS", len(matching_keys) > 1)

    signature_valid = False
    if key is not None:
        _add(
            trust_reasons,
            "ISSUER_MISMATCH",
            key.get("issuer_id") != attestation["issuer_id"],
        )
        _add(
            trust_reasons,
            "KEY_ALGORITHM_MISMATCH",
            key.get("algorithm") != algorithm,
        )
        _add(trust_reasons, "SIGNER_REVOKED", key.get("revoked") is True)

        key_not_before = key.get("not_before_ms")
        key_not_after = key.get("not_after_ms")
        key_interval_valid = (
            _timestamp(key_not_before)
            and _timestamp(key_not_after)
            and key_not_after >= key_not_before
        )
        _add(
            trust_reasons,
            "SIGNER_KEY_VALIDITY_INVALID",
            not key_interval_valid,
        )
        _add(
            trust_reasons,
            "SIGNER_KEY_NOT_CURRENT",
            key_interval_valid
            and (now_ms < key_not_before or now_ms > key_not_after),
        )

        public_key_bytes = (
            _decode_base64(key.get("public_key_base64", ""))
            if _non_empty_string(key.get("public_key_base64"))
            else None
        )
        signature_bytes = _decode_base64(attestation["signature"])
        key_material_valid = (
            public_key_bytes is not None and len(public_key_bytes) == PUBLIC_KEY_BYTES
        )
        signature_material_valid = (
            signature_bytes is not None and len(signature_bytes) == SIGNATURE_BYTES
        )
        _add(
            trust_reasons,
            "TRUST_KEY_MATERIAL_INVALID",
            not key_material_valid,
        )

        if (
            algorithm_allowed
            and key.get("algorithm") == ED25519
            and signature_material_valid
            and key_material_valid
        ):
            try:
                Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(
                    signature_bytes,
                    signed,
                )
                signature_valid = True
            except (InvalidSignature, ValueError):
                signature_valid = False
        _add(
            reasons,
            "SIGNATURE_INVALID",
            not signature_valid and algorithm_allowed and key_material_valid,
        )

    _add(
        trust_reasons,
        "ATTESTATION_VALIDITY_INVALID",
        attestation["not_after_ms"] < attestation["not_before_ms"],
    )
    _add(
        trust_reasons,
        "ATTESTATION_NOT_YET_VALID",
        now_ms < attestation["not_before_ms"],
    )
    _add(
        trust_reasons,
        "ATTESTATION_EXPIRED",
        now_ms > attestation["not_after_ms"],
    )
    _add(
        trust_reasons,
        "ATTESTATION_ISSUED_IN_FUTURE",
        attestation["issued_at_ms"] > now_ms,
    )

    for reason in trust_reasons:
        _add(reasons, reason, True)

    trusted_current_authority = not trust_reasons
    valid = (
        payload_digest_matches
        and attestation_id_valid
        and canonical_profile_valid
        and signature_valid
        and trusted_current_authority
        and not reasons
    )
    return CanonicalEnvelopeResult(
        valid,
        payload_digest_matches,
        attestation_id_valid,
        canonical_profile_valid,
        signature_valid,
        trusted_current_authority,
        signed_payload_base64,
        tuple(reasons),
    )


_PATH_PART_RE = re.compile(r"(?:[A-Za-z_][A-Za-z0-9_-]*|0|[1-9][0-9]*)\Z")


def _fixture_error(detail: str) -> None:
    raise CanonicalizationError("FIXTURE_SCHEMA_INVALID", detail)


def _set_path(document: dict[str, Any], path: str, value: Any) -> None:
    if not _non_empty_string(path):
        _fixture_error("mutation path must be non-empty")
    parts = path.split(".")
    if any(
        part in _DANGEROUS_PATH_PARTS or not _PATH_PART_RE.fullmatch(part)
        for part in parts
    ):
        _fixture_error(f"unsafe mutation path: {path}")

    cursor: Any = document
    for part in parts[:-1]:
        if isinstance(cursor, list):
            if not part.isdigit() or int(part) >= len(cursor):
                _fixture_error(f"missing mutation path: {path}")
            cursor = cursor[int(part)]
        elif isinstance(cursor, dict) and part in cursor:
            cursor = cursor[part]
        else:
            _fixture_error(f"missing mutation path: {path}")

    last = parts[-1]
    if isinstance(cursor, list):
        if not last.isdigit() or int(last) >= len(cursor):
            _fixture_error(f"missing mutation path: {path}")
        previous = cursor[int(last)]
    elif isinstance(cursor, dict) and last in cursor:
        previous = cursor[last]
    else:
        _fixture_error(f"missing mutation path: {path}")

    try:
        previous_bytes = canonical_bytes(previous)
        replacement_bytes = canonical_bytes(value)
    except CanonicalizationError as exc:
        _fixture_error(f"invalid mutation value for {path}: {exc.code}")
    if previous_bytes == replacement_bytes:
        _fixture_error(f"no-op mutation path: {path}")

    if isinstance(cursor, list):
        cursor[int(last)] = copy.deepcopy(value)
    else:
        cursor[last] = copy.deepcopy(value)


def _validate_fixture_shape(fixture: Any) -> None:
    if not _exact_dict(fixture, _FIXTURE_FIELDS):
        _fixture_error("fixture fields")
    if fixture["profile_id"] != PROFILE_ID:
        _fixture_error("profile_id")
    if fixture["schema_version"] != FIXTURE_SCHEMA_VERSION:
        _fixture_error("schema_version")
    if fixture["canonical_profile"] != CANONICAL_PROFILE:
        _fixture_error("canonical_profile")
    if not _timestamp(fixture["base_now_ms"]):
        _fixture_error("base_now_ms")

    envelope = fixture["base_envelope"]
    if not _exact_dict(envelope, _ENVELOPE_FIELDS):
        _fixture_error("base_envelope fields")
    if (
        envelope["profile_id"] != PROFILE_ID
        or envelope["schema_version"] != SCHEMA_VERSION
        or envelope["canonical_profile"] != CANONICAL_PROFILE
        or not isinstance(envelope["payload"], (dict, list))
        or not _exact_dict(envelope["attestation"], _ATTESTATION_FIELDS)
    ):
        _fixture_error("base_envelope values")

    attestation = envelope["attestation"]
    attestation_values_valid = (
        _non_empty_string(attestation["attestation_id"])
        and _hex64(attestation["payload_digest"])
        and _non_empty_string(attestation["issuer_id"])
        and _non_empty_string(attestation["signer_key_id"])
        and _non_empty_string(attestation["trust_root_id"])
        and _timestamp(attestation["issued_at_ms"])
        and _timestamp(attestation["not_before_ms"])
        and _timestamp(attestation["not_after_ms"])
        and attestation["signature_algorithm"] == ED25519
        and _canonical_base64(attestation["signature"], length=SIGNATURE_BYTES)
    )
    if not attestation_values_valid:
        _fixture_error("base_envelope attestation values")
    try:
        canonical_bytes(envelope["payload"])
    except CanonicalizationError as exc:
        _fixture_error(f"base_envelope payload: {exc.code}")

    trust_root = fixture["trust_root"]
    if (
        not _exact_dict(trust_root, _TRUST_ROOT_FIELDS)
        or trust_root["profile_id"] != TRUST_ROOT_PROFILE_ID
        or not _non_empty_string(trust_root["trust_root_id"])
        or trust_root["allowed_algorithms"] != [ED25519]
        or not isinstance(trust_root["keys"], list)
        or not trust_root["keys"]
    ):
        _fixture_error("trust_root values")
    for index, key in enumerate(trust_root["keys"]):
        if (
            not _trust_key_shape_valid(key)
            or key["algorithm"] != ED25519
            or not _canonical_base64(
                key["public_key_base64"], length=PUBLIC_KEY_BYTES
            )
        ):
            _fixture_error(f"trust_root keys[{index}]")

    if not _canonical_base64(fixture["expected_signed_payload_base64"]):
        _fixture_error("expected_signed_payload_base64")
    if not _canonical_base64(
        fixture["expected_signature_base64"], length=SIGNATURE_BYTES
    ):
        _fixture_error("expected_signature_base64")

    cases = fixture["cases"]
    if not isinstance(cases, list) or not cases:
        _fixture_error("cases must be non-empty")
    identifiers: set[str] = set()
    for index, case in enumerate(cases):
        if not _exact_dict(case, _CASE_FIELDS):
            _fixture_error(f"cases[{index}] fields")
        case_id = case["id"]
        if not _non_empty_string(case_id):
            _fixture_error(f"cases[{index}].id")
        if case_id in identifiers:
            _fixture_error(f"duplicate case id: {case_id}")
        identifiers.add(case_id)
        if not _timestamp(case["now_ms"]):
            _fixture_error(f"cases[{index}].now_ms")

        expected = case["expected"]
        if not _exact_dict(expected, _EXPECTED_FIELDS):
            _fixture_error(f"cases[{index}].expected fields")
        boolean_fields = _EXPECTED_FIELDS - {"reason_codes"}
        if not all(isinstance(expected[field], bool) for field in boolean_fields):
            _fixture_error(f"cases[{index}].expected booleans")
        reason_codes = expected["reason_codes"]
        if (
            not isinstance(reason_codes, list)
            or not all(_non_empty_string(reason) for reason in reason_codes)
            or len(set(reason_codes)) != len(reason_codes)
        ):
            _fixture_error(f"cases[{index}].expected reason_codes")

        envelope_copy = copy.deepcopy(envelope)
        trust_root_copy = copy.deepcopy(trust_root)
        for group_name, document in (
            ("envelope_mutations", envelope_copy),
            ("trust_root_mutations", trust_root_copy),
        ):
            mutations = case[group_name]
            if not isinstance(mutations, list):
                _fixture_error(f"cases[{index}].{group_name}")
            for mutation_index, mutation in enumerate(mutations):
                if not _exact_dict(mutation, _MUTATION_FIELDS):
                    _fixture_error(
                        f"cases[{index}].{group_name}[{mutation_index}] fields"
                    )
                _set_path(document, mutation["path"], mutation["value"])


def run_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(fixture, Mapping):
        _fixture_error("fixture root")
    try:
        fixture = copy.deepcopy(dict(fixture))
    except (TypeError, ValueError, copy.Error):
        _fixture_error("fixture snapshot")
    _validate_fixture_shape(fixture)

    results: list[dict[str, Any]] = []
    for case in fixture["cases"]:
        envelope = copy.deepcopy(fixture["base_envelope"])
        trust_root = copy.deepcopy(fixture["trust_root"])
        for mutation in case["envelope_mutations"]:
            _set_path(envelope, mutation["path"], mutation["value"])
        for mutation in case["trust_root_mutations"]:
            _set_path(trust_root, mutation["path"], mutation["value"])

        result = verify_canonical_signed_envelope(
            envelope,
            trust_root,
            now_ms=case["now_ms"],
        )
        actual = {
            "valid": result.valid,
            "payload_digest_matches": result.payload_digest_matches,
            "attestation_id_valid": result.attestation_id_valid,
            "canonical_profile_valid": result.canonical_profile_valid,
            "signature_valid": result.signature_valid,
            "trusted_current_authority": result.trusted_current_authority,
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

    base_result = verify_canonical_signed_envelope(
        copy.deepcopy(fixture["base_envelope"]),
        copy.deepcopy(fixture["trust_root"]),
        now_ms=fixture["base_now_ms"],
    )
    signature = fixture["base_envelope"]["attestation"]["signature"]
    parity = {
        "signed_payload_base64": base_result.signed_payload_base64,
        "signed_payload_matches_expected": (
            base_result.signed_payload_base64
            == fixture["expected_signed_payload_base64"]
        ),
        "signature_base64": signature,
        "signature_matches_expected": signature == fixture["expected_signature_base64"],
    }
    passed = sum(1 for result in results if result["passed"])
    all_passed = (
        base_result.valid
        and passed == len(results)
        and parity["signed_payload_matches_expected"]
        and parity["signature_matches_expected"]
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
        description="Verify VTL v0.11 canonical signed envelope vectors"
    )
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args(argv)

    fixture = strict_loads(args.fixture.read_text(encoding="utf-8"))
    result = run_fixture(fixture)
    serialized_public_evidence = json.dumps(
        result, indent=2, sort_keys=True, ensure_ascii=False
    )
    # Public conformance evidence only: canonical signed bytes and signature.
    # codeql[py/clear-text-logging-sensitive-data]
    print(serialized_public_evidence)
    return 0 if result["summary"]["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
