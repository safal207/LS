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
    return isinstance(value, int) and not isinstance(value, bool)


def _decode_base64(value: str) -> bytes | None:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return None


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
        return CanonicalEnvelopeResult(
            False, False, False, False, False, False, "", ("ENVELOPE_ROOT_INVALID",)
        )
    if not isinstance(trust_root, Mapping):
        return CanonicalEnvelopeResult(
            False, False, False, False, False, False, "", ("TRUST_ROOT_INVALID",)
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

    required = {
        "attestation_id": _non_empty_string,
        "payload_digest": _hex64,
        "issuer_id": _non_empty_string,
        "signer_key_id": _non_empty_string,
        "trust_root_id": _non_empty_string,
        "issued_at_ms": _integer,
        "not_before_ms": _integer,
        "not_after_ms": _integer,
        "signature_algorithm": _non_empty_string,
        "signature": _non_empty_string,
    }
    for field, predicate in required.items():
        if field not in attestation or not predicate(attestation[field]):
            _add(reasons, f"ATTESTATION_SCHEMA_INVALID:{field}", True)

    if any(reason.startswith("ATTESTATION_SCHEMA_INVALID:") for reason in reasons) or (
        "PAYLOAD_INVALID" in reasons
    ):
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

    attestation_id_valid = attestation["attestation_id"] == compute_attestation_id(envelope)
    _add(reasons, "ATTESTATION_ID_INVALID", not attestation_id_valid)

    trust_reasons: list[str] = []
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
    if not isinstance(allowed_algorithms, list) or not all(
        _non_empty_string(value) for value in allowed_algorithms
    ):
        _add(trust_reasons, "TRUST_ROOT_ALGORITHMS_INVALID", True)
        allowed_algorithms = []

    algorithm = attestation["signature_algorithm"]
    algorithm_allowed = algorithm == ED25519 and algorithm in allowed_algorithms
    _add(trust_reasons, "ALGORITHM_NOT_ALLOWED", not algorithm_allowed)

    keys = trust_root.get("keys")
    if not isinstance(keys, list):
        _add(trust_reasons, "TRUST_ROOT_KEYS_INVALID", True)
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
            _integer(key_not_before)
            and _integer(key_not_after)
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
        _add(
            trust_reasons,
            "TRUST_KEY_MATERIAL_INVALID",
            not key_material_valid,
        )

        if (
            algorithm_allowed
            and key.get("algorithm") == ED25519
            and signature_bytes is not None
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
        envelope = copy.deepcopy(fixture["base_envelope"])
        trust_root = copy.deepcopy(fixture["trust_root"])
        for mutation in case.get("envelope_mutations", []):
            _set_path(envelope, mutation["path"], mutation["value"])
        for mutation in case.get("trust_root_mutations", []):
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
        passed == len(results)
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
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["summary"]["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
