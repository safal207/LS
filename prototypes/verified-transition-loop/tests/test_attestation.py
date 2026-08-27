import copy
from pathlib import Path

from verified_transition_loop.attestation import (
    load_fixture,
    run_fixture,
    verify_attested_dispatch,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "attested-dispatch-v0.8.json"
NOW = 1_800_000_001_000


def fixture_data():
    return load_fixture(FIXTURE)


def case_material(case_id: str):
    fixture = fixture_data()
    case = next(item for item in fixture["cases"] if item["id"] == case_id)
    envelope = copy.deepcopy(fixture["base_envelope"])
    trust_root = copy.deepcopy(fixture["trust_root"])

    def set_path(document, path, value):
        parts = path.split(".")
        cursor = document
        for part in parts[:-1]:
            cursor = cursor[part]
        cursor[parts[-1]] = copy.deepcopy(value)

    for mutation in case.get("envelope_mutations", []):
        set_path(envelope, mutation["path"], mutation["value"])
    for mutation in case.get("trust_root_mutations", []):
        set_path(trust_root, mutation["path"], mutation["value"])
    return envelope, trust_root, case["now_ms"]


def test_v08_fixture_vectors_all_pass():
    result = run_fixture(fixture_data())
    assert result["summary"] == {
        "total": 14,
        "passed": 14,
        "failed": 0,
        "all_passed": True,
    }


def test_valid_attestation_separates_all_three_claims():
    envelope, trust_root, now_ms = case_material("valid-trusted-attestation")
    result = verify_attested_dispatch(envelope, trust_root, now_ms=now_ms)

    assert result.valid is True
    assert result.integrity_valid is True
    assert result.transcript_digest_matches is True
    assert result.attestation_id_valid is True
    assert result.signature_valid is True
    assert result.trusted_current_authority is True
    assert result.reason_codes == ()


def test_tampered_transcript_keeps_signature_claim_separate():
    envelope, trust_root, now_ms = case_material("transcript-tampered-after-signing")
    result = verify_attested_dispatch(envelope, trust_root, now_ms=now_ms)

    assert result.valid is False
    assert result.integrity_valid is False
    assert result.transcript_digest_matches is False
    assert result.signature_valid is True
    assert result.trusted_current_authority is True


def test_self_consistent_replacement_still_fails_exact_attested_digest_binding():
    envelope, trust_root, now_ms = case_material("self-consistent-replacement-transcript")
    result = verify_attested_dispatch(envelope, trust_root, now_ms=now_ms)

    assert result.integrity_valid is True
    assert result.signature_valid is True
    assert result.trusted_current_authority is True
    assert result.valid is False
    assert result.reason_codes == ("ATTESTED_TRANSCRIPT_DIGEST_MISMATCH",)


def test_revocation_is_authority_failure_not_signature_failure():
    envelope, trust_root, now_ms = case_material("revoked-signer")
    result = verify_attested_dispatch(envelope, trust_root, now_ms=now_ms)

    assert result.integrity_valid is True
    assert result.signature_valid is True
    assert result.trusted_current_authority is False
    assert result.reason_codes == ("SIGNER_REVOKED",)


def test_valid_signature_cannot_override_invalid_v07_transcript():
    envelope, trust_root, now_ms = case_material("valid-signature-over-invalid-v07-transcript")
    result = verify_attested_dispatch(envelope, trust_root, now_ms=now_ms)

    assert result.integrity_valid is False
    assert result.transcript_digest_matches is True
    assert result.signature_valid is True
    assert result.trusted_current_authority is True
    assert result.valid is False
    assert result.reason_codes == ("TRANSCRIPT_INTEGRITY_INVALID",)


def test_unknown_signer_is_not_promoted_by_transcript_claims():
    envelope, trust_root, now_ms = case_material("unknown-signer")
    result = verify_attested_dispatch(envelope, trust_root, now_ms=now_ms)

    assert result.integrity_valid is True
    assert result.signature_valid is False
    assert result.trusted_current_authority is False
    assert result.reason_codes == ("SIGNER_NOT_TRUSTED",)
