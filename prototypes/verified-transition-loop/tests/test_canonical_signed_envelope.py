from __future__ import annotations

import base64
import copy
import json
from pathlib import Path

from verified_transition_loop.canonical_signed_envelope import (
    CANONICAL_PROFILE,
    run_fixture,
    verify_canonical_signed_envelope,
)

FIXTURE = Path(__file__).parents[1] / "fixtures" / "canonical-signed-envelope-v0.11.json"


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
