from __future__ import annotations

import base64
import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import verified_transition_loop.canonical_signed_envelope as envelope_module
from verified_transition_loop.canonical_signed_envelope import (
    CANONICAL_PROFILE,
    CanonicalizationError,
    run_fixture,
    verify_canonical_signed_envelope,
)

FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "canonical-signed-envelope-v0.11.json"
)
SCHEMA = (
    Path(__file__).parents[1]
    / "schemas"
    / "canonical-signed-envelope-v0.11.schema.json"
)


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_machine_readable_fixture_passes_all_vectors() -> None:
    result = run_fixture(_fixture())
    assert result["canonical_profile"] == CANONICAL_PROFILE
    assert result["summary"] == {
        "total": 12,
        "passed": 12,
        "failed": 0,
        "all_passed": True,
    }


def test_fixture_binds_exact_signed_bytes_and_signature() -> None:
    result = run_fixture(_fixture())
    assert result["parity"]["signed_payload_matches_expected"] is True
    assert result["parity"]["signature_matches_expected"] is True


def test_fixture_matches_published_schema() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    fixture = _fixture()

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(fixture)


def test_payload_tamper_does_not_rewrite_signature_claim() -> None:
    fixture = _fixture()
    envelope = copy.deepcopy(fixture["base_envelope"])
    envelope["payload"]["action"]["payload"]["commit"] = "def456"
    result = verify_canonical_signed_envelope(
        envelope, fixture["trust_root"], now_ms=fixture["base_now_ms"]
    )
    assert result.valid is False
    assert result.payload_digest_matches is False
    assert result.signature_valid is True
    assert result.reason_codes == ("PAYLOAD_DIGEST_MISMATCH",)


def test_canonical_profile_is_signature_bound() -> None:
    fixture = _fixture()
    envelope = copy.deepcopy(fixture["base_envelope"])
    envelope["canonical_profile"] = "rfc8785-safe-integer/v0.9"
    result = verify_canonical_signed_envelope(
        envelope, fixture["trust_root"], now_ms=fixture["base_now_ms"]
    )
    assert result.valid is False
    assert result.canonical_profile_valid is False
    assert result.attestation_id_valid is False
    assert result.signature_valid is False
    assert result.reason_codes == (
        "CANONICAL_PROFILE_MISMATCH",
        "ATTESTATION_ID_INVALID",
        "SIGNATURE_INVALID",
    )


def test_revocation_is_separate_from_signature_math() -> None:
    fixture = _fixture()
    trust = copy.deepcopy(fixture["trust_root"])
    trust["keys"][0]["revoked"] = True
    result = verify_canonical_signed_envelope(
        fixture["base_envelope"], trust, now_ms=fixture["base_now_ms"]
    )
    assert result.signature_valid is True
    assert result.trusted_current_authority is False
    assert result.reason_codes == ("SIGNER_REVOKED",)


def test_wrong_public_key_fails_signature() -> None:
    fixture = _fixture()
    trust = copy.deepcopy(fixture["trust_root"])
    trust["keys"][0]["public_key_base64"] = base64.b64encode(
        bytes(reversed(range(32)))
    ).decode()
    result = verify_canonical_signed_envelope(
        fixture["base_envelope"], trust, now_ms=fixture["base_now_ms"]
    )
    assert result.signature_valid is False
    assert result.reason_codes == ("SIGNATURE_INVALID",)


def test_ambiguous_signer_id_fails_closed() -> None:
    fixture = _fixture()
    trust = copy.deepcopy(fixture["trust_root"])
    trust["keys"].append(copy.deepcopy(trust["keys"][0]))
    result = verify_canonical_signed_envelope(
        fixture["base_envelope"], trust, now_ms=fixture["base_now_ms"]
    )
    assert result.valid is False
    assert result.signature_valid is False
    assert result.trusted_current_authority is False
    assert result.reason_codes == ("SIGNER_KEY_AMBIGUOUS",)


def test_malformed_public_key_fails_closed_without_signature_claim() -> None:
    fixture = _fixture()
    trust = copy.deepcopy(fixture["trust_root"])
    trust["keys"][0]["public_key_base64"] = "not-base64"
    result = verify_canonical_signed_envelope(
        fixture["base_envelope"], trust, now_ms=fixture["base_now_ms"]
    )
    assert result.valid is False
    assert result.signature_valid is False
    assert result.reason_codes == ("TRUST_KEY_MATERIAL_INVALID",)


def test_unsafe_integer_payload_fails_canonicalization() -> None:
    fixture = _fixture()
    envelope = copy.deepcopy(fixture["base_envelope"])
    envelope["payload"]["attempt"] = 9_007_199_254_740_992
    result = verify_canonical_signed_envelope(
        envelope, fixture["trust_root"], now_ms=fixture["base_now_ms"]
    )
    assert result.valid is False
    assert result.reason_codes == ("CANONICALIZATION_ERROR:INTEGER_OUT_OF_RANGE",)


def test_float_payload_fails_canonicalization() -> None:
    fixture = _fixture()
    envelope = copy.deepcopy(fixture["base_envelope"])
    envelope["payload"]["attempt"] = 1.5
    result = verify_canonical_signed_envelope(
        envelope, fixture["trust_root"], now_ms=fixture["base_now_ms"]
    )
    assert result.valid is False
    assert result.reason_codes == ("CANONICALIZATION_ERROR:UNSUPPORTED_NUMBER",)


def test_expiry_does_not_invalidate_signature_math() -> None:
    fixture = _fixture()
    result = verify_canonical_signed_envelope(
        fixture["base_envelope"], fixture["trust_root"], now_ms=1_800_003_600_001
    )
    assert result.valid is False
    assert result.signature_valid is True
    assert result.trusted_current_authority is False
    assert result.reason_codes == ("ATTESTATION_EXPIRED",)


@pytest.mark.parametrize(
    ("target", "reason", "authority_valid"),
    (
        ("envelope", "ENVELOPE_SCHEMA_INVALID", True),
        ("attestation", "ATTESTATION_SCHEMA_INVALID:fields", True),
        ("trust_root", "TRUST_ROOT_SCHEMA_INVALID", False),
        ("trust_key", "TRUST_ROOT_KEYS_INVALID", False),
    ),
)
def test_unpublished_fields_fail_closed_without_collapsing_signature_math(
    target: str,
    reason: str,
    authority_valid: bool,
) -> None:
    fixture = _fixture()
    envelope = copy.deepcopy(fixture["base_envelope"])
    trust_root = copy.deepcopy(fixture["trust_root"])
    if target == "envelope":
        envelope["unsigned_claim"] = "ignored-by-signature"
    elif target == "attestation":
        envelope["attestation"]["unsigned_claim"] = "ignored-by-signature"
    elif target == "trust_root":
        trust_root["unpublished_policy"] = "permit"
    else:
        trust_root["keys"][0]["unpublished_policy"] = "permit"

    result = verify_canonical_signed_envelope(
        envelope, trust_root, now_ms=fixture["base_now_ms"]
    )

    assert result.valid is False
    assert result.signature_valid is True
    assert result.trusted_current_authority is authority_valid
    assert result.reason_codes == (reason,)


def test_revoked_must_be_boolean() -> None:
    fixture = _fixture()
    trust_root = copy.deepcopy(fixture["trust_root"])
    trust_root["keys"][0]["revoked"] = "false"

    result = verify_canonical_signed_envelope(
        fixture["base_envelope"], trust_root, now_ms=fixture["base_now_ms"]
    )

    assert result.valid is False
    assert result.signature_valid is True
    assert result.trusted_current_authority is False
    assert result.reason_codes == ("TRUST_ROOT_KEYS_INVALID",)


@pytest.mark.parametrize("now_ms", (-1, True, 9_007_199_254_740_992))
def test_verifier_time_must_be_non_negative_safe_integer(now_ms: int) -> None:
    fixture = _fixture()
    result = verify_canonical_signed_envelope(
        fixture["base_envelope"], fixture["trust_root"], now_ms=now_ms
    )
    assert result.reason_codes == ("VERIFIER_TIME_INVALID",)


def test_negative_attestation_time_fails_schema_boundary() -> None:
    fixture = _fixture()
    envelope = copy.deepcopy(fixture["base_envelope"])
    envelope["attestation"]["issued_at_ms"] = -1

    result = verify_canonical_signed_envelope(
        envelope, fixture["trust_root"], now_ms=fixture["base_now_ms"]
    )

    assert result.valid is False
    assert result.reason_codes == ("ATTESTATION_SCHEMA_INVALID:issued_at_ms",)


def test_negative_key_time_cannot_be_current_authority() -> None:
    fixture = _fixture()
    trust_root = copy.deepcopy(fixture["trust_root"])
    trust_root["keys"][0]["not_before_ms"] = -1

    result = verify_canonical_signed_envelope(
        fixture["base_envelope"], trust_root, now_ms=fixture["base_now_ms"]
    )

    assert result.signature_valid is True
    assert result.trusted_current_authority is False
    assert result.reason_codes == (
        "TRUST_ROOT_KEYS_INVALID",
        "SIGNER_KEY_VALIDITY_INVALID",
    )


@pytest.mark.parametrize(
    "signature",
    (
        "AQ==",
        "R7TH2uDvWdDRGmsY+V/erD2Iyy/QV3eff3LHUUwDec1Rg9bwXNvSRxQvVZU8ThXywdJ/"
        "Wyex7K1Yggd0dBDoDA==\n",
    ),
)
def test_signature_requires_canonical_ed25519_material(signature: str) -> None:
    fixture = _fixture()
    envelope = copy.deepcopy(fixture["base_envelope"])
    envelope["attestation"]["signature"] = signature

    result = verify_canonical_signed_envelope(
        envelope, fixture["trust_root"], now_ms=fixture["base_now_ms"]
    )

    assert result.valid is False
    assert result.signature_valid is False
    assert result.reason_codes == ("SIGNATURE_INVALID",)


def test_verifier_snapshots_caller_inputs_once(monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _fixture()
    envelope = copy.deepcopy(fixture["base_envelope"])
    trust_root = copy.deepcopy(fixture["trust_root"])
    original_sha256 = envelope_module.canonical_sha256

    def mutate_callers_after_snapshot(value: object) -> str:
        envelope["attestation"]["signature"] = base64.b64encode(bytes(64)).decode()
        trust_root["keys"][0]["revoked"] = True
        return original_sha256(value)

    monkeypatch.setattr(
        envelope_module, "canonical_sha256", mutate_callers_after_snapshot
    )
    result = verify_canonical_signed_envelope(
        envelope, trust_root, now_ms=fixture["base_now_ms"]
    )

    assert result.valid is True
    assert envelope["attestation"]["signature"] != fixture["expected_signature_base64"]
    assert trust_root["keys"][0]["revoked"] is True


@pytest.mark.parametrize(
    "mutation",
    (
        "extra_root_field",
        "empty_cases",
        "duplicate_case_id",
        "extra_case_field",
        "dangerous_path",
        "missing_path",
        "no_op_mutation",
    ),
)
def test_fixture_contract_fails_closed(mutation: str) -> None:
    fixture = _fixture()
    if mutation == "extra_root_field":
        fixture["claimed_valid"] = True
    elif mutation == "empty_cases":
        fixture["cases"] = []
    elif mutation == "duplicate_case_id":
        fixture["cases"][1]["id"] = fixture["cases"][0]["id"]
    elif mutation == "extra_case_field":
        fixture["cases"][0]["claimed_valid"] = True
    elif mutation == "dangerous_path":
        fixture["cases"][0]["envelope_mutations"] = [
            {"path": "__proto__.polluted", "value": True}
        ]
    elif mutation == "missing_path":
        fixture["cases"][0]["envelope_mutations"] = [
            {"path": "payload.missing", "value": True}
        ]
    else:
        fixture["cases"][0]["envelope_mutations"] = [
            {"path": "payload.attempt", "value": 1}
        ]

    with pytest.raises(CanonicalizationError) as excinfo:
        run_fixture(fixture)
    assert excinfo.value.code == "FIXTURE_SCHEMA_INVALID"


def test_invalid_base_cannot_produce_all_passed_fixture() -> None:
    fixture = _fixture()
    invalid_signature = base64.b64encode(bytes(64)).decode()
    fixture["base_envelope"]["attestation"]["signature"] = invalid_signature
    fixture["expected_signature_base64"] = invalid_signature
    fixture["cases"] = [
        {
            "id": "invalid-base",
            "now_ms": fixture["base_now_ms"],
            "envelope_mutations": [],
            "trust_root_mutations": [],
            "expected": {
                "valid": False,
                "payload_digest_matches": True,
                "attestation_id_valid": True,
                "canonical_profile_valid": True,
                "signature_valid": False,
                "trusted_current_authority": True,
                "reason_codes": ["SIGNATURE_INVALID"],
            },
        }
    ]

    result = run_fixture(fixture)

    assert result["cases"][0]["passed"] is True
    assert result["parity"]["signed_payload_matches_expected"] is True
    assert result["parity"]["signature_matches_expected"] is True
    assert result["summary"] == {
        "total": 1,
        "passed": 1,
        "failed": 0,
        "all_passed": False,
    }
