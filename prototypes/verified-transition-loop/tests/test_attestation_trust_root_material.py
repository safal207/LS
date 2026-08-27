import copy
from pathlib import Path

from verified_transition_loop.attestation import load_fixture, verify_attested_dispatch

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "attested-dispatch-v0.8.json"
NOW = 1_800_000_001_000


def base_inputs():
    fixture = load_fixture(FIXTURE)
    return (
        copy.deepcopy(fixture["base_envelope"]),
        copy.deepcopy(fixture["trust_root"]),
    )


def test_malformed_trust_root_public_key_is_authority_failure():
    envelope, trust_root = base_inputs()
    trust_root["keys"][0]["public_key_base64"] = "not-base64!"

    result = verify_attested_dispatch(envelope, trust_root, now_ms=NOW)

    assert result.valid is False
    assert result.integrity_valid is True
    assert result.signature_valid is False
    assert result.trusted_current_authority is False
    assert result.reason_codes == ("TRUST_KEY_MATERIAL_INVALID",)


def test_wrong_length_ed25519_public_key_is_authority_failure():
    envelope, trust_root = base_inputs()
    trust_root["keys"][0]["public_key_base64"] = "AA=="

    result = verify_attested_dispatch(envelope, trust_root, now_ms=NOW)

    assert result.valid is False
    assert result.signature_valid is False
    assert result.trusted_current_authority is False
    assert result.reason_codes == ("TRUST_KEY_MATERIAL_INVALID",)


def test_inverted_signer_key_validity_interval_fails_closed():
    envelope, trust_root = base_inputs()
    key = trust_root["keys"][0]
    key["not_before_ms"] = NOW + 1000
    key["not_after_ms"] = NOW - 1000

    result = verify_attested_dispatch(envelope, trust_root, now_ms=NOW)

    assert result.valid is False
    assert result.integrity_valid is True
    assert result.signature_valid is True
    assert result.trusted_current_authority is False
    assert result.reason_codes == ("SIGNER_KEY_VALIDITY_INVALID",)
