from __future__ import annotations

import argparse
import base64
import binascii
import copy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .dispatch_receipt import verify_dispatch_transcript

PROFILE_ID = "vtl-attested-dispatch-v0.8"
SCHEMA_VERSION = "vtl.attested-dispatch/v0.8"
FIXTURE_SCHEMA_VERSION = "vtl.attested-dispatch-fixture/v0.8"
TRUST_ROOT_PROFILE_ID = "vtl-trust-root/v0.8"
ED25519 = "ED25519"


@dataclass(frozen=True)
class AuthenticityResult:
    valid: bool
    integrity_valid: bool
    transcript_digest_matches: bool
    attestation_id_valid: bool
    signature_valid: bool
    trusted_current_authority: bool
    reason_codes: tuple[str, ...]


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _stable_id(prefix: str, value: Any) -> str:
    return f"{prefix}_{_digest(value)[:24]}"


def transcript_digest(transcript: Mapping[str, Any]) -> str:
    return _digest(dict(transcript))


_STATEMENT_FIELDS = (
    "profile_id",
    "schema_version",
    "transcript_digest",
    "issuer_id",
    "signer_key_id",
    "trust_root_id",
    "issued_at_ms",
    "not_before_ms",
    "not_after_ms",
    "trust_policy_version",
    "signature_algorithm",
)


def attestation_statement(attestation: Mapping[str, Any]) -> dict[str, Any]:
    return {field: attestation.get(field) for field in _STATEMENT_FIELDS}


def compute_attestation_id(attestation: Mapping[str, Any]) -> str:
    return _stable_id("attest", attestation_statement(attestation))


def signed_attestation_payload(attestation: Mapping[str, Any]) -> bytes:
    return _canonical_json(
        {
            "attestation_id": attestation.get("attestation_id"),
            **attestation_statement(attestation),
        }
    )


def _add(reasons: list[str], reason: str, condition: bool) -> None:
    if condition and reason not in reasons:
        reasons.append(reason)


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _hex64(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdef" for ch in value)
    )


def validate_attested_envelope_shape(envelope: Any) -> tuple[str, ...]:
    if not isinstance(envelope, Mapping):
        return ("ENVELOPE_ROOT_INVALID",)

    reasons: list[str] = []
    _add(reasons, "PROFILE_ID_MISMATCH", envelope.get("profile_id") != PROFILE_ID)
    _add(reasons, "SCHEMA_VERSION_MISMATCH", envelope.get("schema_version") != SCHEMA_VERSION)
    _add(reasons, "TRANSCRIPT_SECTION_INVALID", not isinstance(envelope.get("transcript"), Mapping))
    attestation = envelope.get("attestation")
    _add(reasons, "ATTESTATION_SECTION_INVALID", not isinstance(attestation, Mapping))
    if reasons:
        return tuple(reasons)

    required = {
        "attestation_id": _non_empty_string,
        "profile_id": lambda value: value == PROFILE_ID,
        "schema_version": lambda value: value == SCHEMA_VERSION,
        "transcript_digest": _hex64,
        "issuer_id": _non_empty_string,
        "signer_key_id": _non_empty_string,
        "trust_root_id": _non_empty_string,
        "issued_at_ms": _integer,
        "not_before_ms": _integer,
        "not_after_ms": _integer,
        "trust_policy_version": _non_empty_string,
        "signature_algorithm": _non_empty_string,
        "signature": _non_empty_string,
    }
    for field, predicate in required.items():
        if field not in attestation or not predicate(attestation[field]):
            _add(reasons, f"ATTESTATION_SCHEMA_INVALID:{field}", True)
    return tuple(reasons)


def validate_trust_root_shape(trust_root: Any) -> tuple[str, ...]:
    if not isinstance(trust_root, Mapping):
        return ("TRUST_ROOT_INVALID",)
    reasons: list[str] = []
    _add(
        reasons,
        "TRUST_ROOT_PROFILE_INVALID",
        trust_root.get("profile_id") != TRUST_ROOT_PROFILE_ID,
    )
    for field in ("trust_root_id", "policy_version"):
        _add(
            reasons,
            f"TRUST_ROOT_SCHEMA_INVALID:{field}",
            not _non_empty_string(trust_root.get(field)),
        )
    algorithms = trust_root.get("allowed_algorithms")
    _add(
        reasons,
        "TRUST_ROOT_SCHEMA_INVALID:allowed_algorithms",
        not isinstance(algorithms, list)
        or not algorithms
        or not all(_non_empty_string(value) for value in algorithms),
    )
    keys = trust_root.get("keys")
    if not isinstance(keys, list) or not keys:
        _add(reasons, "TRUST_ROOT_SCHEMA_INVALID:keys", True)
        return tuple(reasons)
    for index, key in enumerate(keys):
        if not isinstance(key, Mapping):
            _add(reasons, f"TRUST_KEY_INVALID:{index}", True)
            continue
        specs = {
            "signer_key_id": _non_empty_string,
            "issuer_id": _non_empty_string,
            "algorithm": _non_empty_string,
            "public_key_base64": _non_empty_string,
            "not_before_ms": _integer,
            "not_after_ms": _integer,
            "revoked": lambda value: isinstance(value, bool),
        }
        for field, predicate in specs.items():
            if field not in key or not predicate(key[field]):
                _add(reasons, f"TRUST_KEY_SCHEMA_INVALID:{index}.{field}", True)
    return tuple(reasons)


def _decode_base64(value: str) -> bytes | None:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return None


def verify_attested_dispatch(
    envelope: Any,
    trust_root: Any,
    *,
    now_ms: int,
) -> AuthenticityResult:
    reasons = list(validate_attested_envelope_shape(envelope))
    trust_shape_reasons = validate_trust_root_shape(trust_root)
    reasons.extend(reason for reason in trust_shape_reasons if reason not in reasons)
    if reasons:
        return AuthenticityResult(
            valid=False,
            integrity_valid=False,
            transcript_digest_matches=False,
            attestation_id_valid=False,
            signature_valid=False,
            trusted_current_authority=False,
            reason_codes=tuple(reasons),
        )

    transcript = dict(envelope["transcript"])
    attestation = dict(envelope["attestation"])
    integrity_result = verify_dispatch_transcript(transcript)
    integrity_valid = integrity_result.valid
    _add(reasons, "TRANSCRIPT_INTEGRITY_INVALID", not integrity_valid)

    actual_digest = transcript_digest(transcript)
    digest_matches = attestation["transcript_digest"] == actual_digest
    _add(reasons, "ATTESTED_TRANSCRIPT_DIGEST_MISMATCH", not digest_matches)

    expected_attestation_id = compute_attestation_id(attestation)
    attestation_id_valid = attestation["attestation_id"] == expected_attestation_id
    _add(reasons, "ATTESTATION_ID_INVALID", not attestation_id_valid)

    trust_reasons: list[str] = []
    _add(
        trust_reasons,
        "TRUST_ROOT_MISMATCH",
        attestation["trust_root_id"] != trust_root["trust_root_id"],
    )
    _add(
        trust_reasons,
        "TRUST_POLICY_VERSION_MISMATCH",
        attestation["trust_policy_version"] != trust_root["policy_version"],
    )

    algorithm = attestation["signature_algorithm"]
    allowed_algorithms = trust_root["allowed_algorithms"]
    algorithm_allowed = algorithm in allowed_algorithms and algorithm == ED25519
    _add(trust_reasons, "ALGORITHM_NOT_ALLOWED", not algorithm_allowed)

    matching_keys = [
        candidate
        for candidate in trust_root["keys"]
        if candidate["signer_key_id"] == attestation["signer_key_id"]
    ]
    key = matching_keys[0] if len(matching_keys) == 1 else None
    _add(trust_reasons, "SIGNER_NOT_TRUSTED", len(matching_keys) == 0)
    _add(trust_reasons, "SIGNER_KEY_AMBIGUOUS", len(matching_keys) > 1)

    signature_valid = False
    if key is not None:
        _add(
            trust_reasons,
            "ISSUER_MISMATCH",
            key["issuer_id"] != attestation["issuer_id"],
        )
        _add(
            trust_reasons,
            "KEY_ALGORITHM_MISMATCH",
            key["algorithm"] != algorithm,
        )
        _add(trust_reasons, "SIGNER_REVOKED", key["revoked"] is True)
        _add(
            trust_reasons,
            "SIGNER_KEY_NOT_CURRENT",
            now_ms < key["not_before_ms"] or now_ms > key["not_after_ms"],
        )

        signature_bytes = _decode_base64(attestation["signature"])
        public_key_bytes = _decode_base64(key["public_key_base64"])
        if algorithm_allowed and key["algorithm"] == ED25519 and signature_bytes and public_key_bytes:
            try:
                Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(
                    signature_bytes,
                    signed_attestation_payload(attestation),
                )
                signature_valid = True
            except (InvalidSignature, ValueError):
                signature_valid = False
        _add(reasons, "SIGNATURE_INVALID", not signature_valid and algorithm_allowed)

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
    _add(
        trust_reasons,
        "ATTESTATION_VALIDITY_INVALID",
        attestation["not_after_ms"] < attestation["not_before_ms"],
    )

    for reason in trust_reasons:
        _add(reasons, reason, True)

    trusted_current_authority = not trust_reasons
    valid = (
        integrity_valid
        and digest_matches
        and attestation_id_valid
        and signature_valid
        and trusted_current_authority
        and not reasons
    )
    return AuthenticityResult(
        valid=valid,
        integrity_valid=integrity_valid,
        transcript_digest_matches=digest_matches,
        attestation_id_valid=attestation_id_valid,
        signature_valid=signature_valid,
        trusted_current_authority=trusted_current_authority,
        reason_codes=tuple(reasons),
    )


def _set_path(document: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cursor: Any = document
    for part in parts[:-1]:
        if not isinstance(cursor, dict) or part not in cursor:
            raise ValueError(f"mutation path not found: {path}")
        cursor = cursor[part]
    if not isinstance(cursor, dict) or parts[-1] not in cursor:
        raise ValueError(f"mutation path not found: {path}")
    cursor[parts[-1]] = copy.deepcopy(value)


def validate_fixture_shape(fixture: Any) -> None:
    if not isinstance(fixture, Mapping):
        raise ValueError("fixture root must be an object")
    if fixture.get("profile_id") != PROFILE_ID:
        raise ValueError("fixture profile_id mismatch")
    if fixture.get("schema_version") != FIXTURE_SCHEMA_VERSION:
        raise ValueError("fixture schema_version mismatch")
    if validate_attested_envelope_shape(fixture.get("base_envelope")):
        raise ValueError("fixture base_envelope invalid")
    if validate_trust_root_shape(fixture.get("trust_root")):
        raise ValueError("fixture trust_root invalid")
    cases = fixture.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("fixture cases must be a non-empty list")
    for case in cases:
        if not isinstance(case, Mapping) or not _non_empty_string(case.get("id")):
            raise ValueError("fixture case id missing")
        if not _integer(case.get("now_ms")):
            raise ValueError(f"fixture case {case.get('id')} now_ms invalid")
        for bucket in ("envelope_mutations", "trust_root_mutations"):
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
        if not isinstance(reason_codes, list) or not all(isinstance(value, str) for value in reason_codes):
            raise ValueError(f"fixture case {case['id']} reason_codes invalid")


def load_fixture(path: str | Path) -> dict[str, Any]:
    fixture = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_fixture_shape(fixture)
    return fixture


def run_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    validate_fixture_shape(fixture)
    results: list[dict[str, Any]] = []
    for case in fixture["cases"]:
        envelope = copy.deepcopy(fixture["base_envelope"])
        trust_root = copy.deepcopy(fixture["trust_root"])
        for mutation in case.get("envelope_mutations", []):
            _set_path(envelope, mutation["path"], mutation["value"])
        for mutation in case.get("trust_root_mutations", []):
            _set_path(trust_root, mutation["path"], mutation["value"])
        result = verify_attested_dispatch(envelope, trust_root, now_ms=case["now_ms"])
        expected = case["expected"]
        expected_reasons = tuple(expected["reason_codes"])
        passed = result.valid is expected["valid"] and result.reason_codes == expected_reasons
        results.append(
            {
                "id": case["id"],
                "passed": passed,
                "actual": {
                    "valid": result.valid,
                    "integrity_valid": result.integrity_valid,
                    "signature_valid": result.signature_valid,
                    "trusted_current_authority": result.trusted_current_authority,
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
        description="Verify a VTL v0.8 attested dispatch envelope against an external trust root."
    )
    parser.add_argument("path", help="Attested envelope or v0.8 fixture JSON")
    parser.add_argument("--trust-root", help="Verifier-controlled trust-root JSON")
    parser.add_argument("--now-ms", type=int, help="Verification time in epoch milliseconds")
    args = parser.parse_args(argv)

    data = json.loads(Path(args.path).read_text(encoding="utf-8"))
    if isinstance(data, Mapping) and data.get("schema_version") == FIXTURE_SCHEMA_VERSION:
        result = run_fixture(data)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["summary"]["all_passed"] else 1

    if args.trust_root is None or args.now_ms is None:
        parser.error("--trust-root and --now-ms are required for a single envelope")
    trust_root = json.loads(Path(args.trust_root).read_text(encoding="utf-8"))
    result = verify_attested_dispatch(data, trust_root, now_ms=args.now_ms)
    print(
        json.dumps(
            {
                "profile_id": PROFILE_ID,
                "schema_version": SCHEMA_VERSION,
                "valid": result.valid,
                "integrity_valid": result.integrity_valid,
                "transcript_digest_matches": result.transcript_digest_matches,
                "attestation_id_valid": result.attestation_id_valid,
                "signature_valid": result.signature_valid,
                "trusted_current_authority": result.trusted_current_authority,
                "reason_codes": list(result.reason_codes),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
