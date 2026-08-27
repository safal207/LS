import copy
import json
from pathlib import Path

import verified_transition_loop.trust_snapshot as trust_snapshot_module
from verified_transition_loop.trust_snapshot import (
    load_fixture,
    run_fixture,
    verify_attested_dispatch_with_snapshot,
    verify_trust_root_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "trust-root-snapshot-v0.9.json"
ATTESTATION_FIXTURE = ROOT / "fixtures" / "attested-dispatch-v0.8.json"
NOW = 1_800_000_001_000


def fixture_data():
    return load_fixture(FIXTURE)


def set_path(document, path, value):
    parts = path.split(".")
    cursor = document
    for part in parts[:-1]:
        if isinstance(cursor, list) and part.isdigit():
            cursor = cursor[int(part)]
        else:
            cursor = cursor[part]
    final = parts[-1]
    if isinstance(cursor, list) and final.isdigit():
        cursor[int(final)] = copy.deepcopy(value)
    else:
        cursor[final] = copy.deepcopy(value)


def materialize_case(case_id):
    fixture = fixture_data()
    case = next(item for item in fixture["cases"] if item["id"] == case_id)
    snapshot = copy.deepcopy(fixture["base_snapshot"])
    bootstrap = copy.deepcopy(fixture["bootstrap_authority"])
    checkpoint = copy.deepcopy(fixture["base_checkpoint"])
    for mutation in case.get("snapshot_mutations", []):
        set_path(snapshot, mutation["path"], mutation["value"])
    for mutation in case.get("bootstrap_authority_mutations", []):
        set_path(bootstrap, mutation["path"], mutation["value"])
    for mutation in case.get("checkpoint_mutations", []):
        set_path(checkpoint, mutation["path"], mutation["value"])
    return snapshot, bootstrap, checkpoint, case["now_ms"]


def test_v09_fixture_vectors_all_pass():
    result = run_fixture(fixture_data())
    assert result["summary"] == {
        "total": 14,
        "passed": 14,
        "failed": 0,
        "all_passed": True,
    }


def test_valid_snapshot_separates_all_four_claims():
    snapshot, bootstrap, checkpoint, now_ms = materialize_case("valid-fresh-snapshot")
    result = verify_trust_root_snapshot(
        snapshot, bootstrap, checkpoint, now_ms=now_ms
    )

    assert result.valid is True
    assert result.snapshot_integrity_valid is True
    assert result.bootstrap_signature_valid is True
    assert result.bootstrap_authority_valid is True
    assert result.freshness_valid is True
    assert result.continuity_valid is True
    assert result.reason_codes == ()


def test_old_signed_snapshot_is_valid_signature_but_rejected_as_rollback():
    snapshot, bootstrap, checkpoint, now_ms = materialize_case(
        "old-signed-snapshot-replay-after-newer-checkpoint"
    )
    result = verify_trust_root_snapshot(
        snapshot, bootstrap, checkpoint, now_ms=now_ms
    )

    assert result.snapshot_integrity_valid is True
    assert result.bootstrap_signature_valid is True
    assert result.bootstrap_authority_valid is True
    assert result.freshness_valid is True
    assert result.continuity_valid is False
    assert result.reason_codes == ("SNAPSHOT_ROLLBACK",)


def test_same_generation_different_digest_is_fork_not_signature_failure():
    snapshot, bootstrap, checkpoint, now_ms = materialize_case(
        "same-generation-different-digest-fork"
    )
    result = verify_trust_root_snapshot(
        snapshot, bootstrap, checkpoint, now_ms=now_ms
    )

    assert result.snapshot_integrity_valid is True
    assert result.bootstrap_signature_valid is True
    assert result.freshness_valid is True
    assert result.continuity_valid is False
    assert result.reason_codes == ("SNAPSHOT_FORK_DETECTED",)


def test_trust_root_payload_tamper_does_not_invalidate_historical_signature_claim():
    snapshot, bootstrap, checkpoint, now_ms = materialize_case(
        "trust-root-payload-tamper"
    )
    result = verify_trust_root_snapshot(
        snapshot, bootstrap, checkpoint, now_ms=now_ms
    )

    assert result.snapshot_integrity_valid is False
    assert result.bootstrap_signature_valid is True
    assert result.bootstrap_authority_valid is True
    assert result.freshness_valid is True
    assert result.continuity_valid is True
    assert result.reason_codes == ("TRUST_ROOT_DIGEST_MISMATCH",)


def test_unknown_bootstrap_key_is_authority_failure():
    snapshot, bootstrap, checkpoint, now_ms = materialize_case(
        "unknown-bootstrap-key"
    )
    result = verify_trust_root_snapshot(
        snapshot, bootstrap, checkpoint, now_ms=now_ms
    )

    assert result.snapshot_integrity_valid is True
    assert result.bootstrap_signature_valid is False
    assert result.bootstrap_authority_valid is False
    assert result.reason_codes == ("BOOTSTRAP_KEY_NOT_TRUSTED",)


def test_fresh_snapshot_cannot_rescue_invalid_v08_attestation():
    fixture = fixture_data()
    snapshot = copy.deepcopy(fixture["base_snapshot"])
    bootstrap = copy.deepcopy(fixture["bootstrap_authority"])
    checkpoint = copy.deepcopy(fixture["base_checkpoint"])

    attestation_fixture = json.loads(
        ATTESTATION_FIXTURE.read_text(encoding="utf-8")
    )
    envelope = copy.deepcopy(attestation_fixture["base_envelope"])
    signature = envelope["attestation"]["signature"]
    envelope["attestation"]["signature"] = (
        ("A" if signature[0] != "A" else "B") + signature[1:]
    )

    result = verify_attested_dispatch_with_snapshot(
        snapshot,
        bootstrap,
        checkpoint,
        envelope,
        now_ms=NOW,
    )

    assert result.snapshot.valid is True
    assert result.attested_dispatch is not None
    assert result.attested_dispatch.integrity_valid is True
    assert result.attested_dispatch.signature_valid is False
    assert result.attested_dispatch.valid is False
    assert result.attested_dispatch.reason_codes == ("SIGNATURE_INVALID",)
    assert result.valid is False


def test_fresh_snapshot_and_valid_v08_attestation_compose_successfully():
    fixture = fixture_data()
    attestation_fixture = json.loads(
        ATTESTATION_FIXTURE.read_text(encoding="utf-8")
    )
    result = verify_attested_dispatch_with_snapshot(
        copy.deepcopy(fixture["base_snapshot"]),
        copy.deepcopy(fixture["bootstrap_authority"]),
        copy.deepcopy(fixture["base_checkpoint"]),
        copy.deepcopy(attestation_fixture["base_envelope"]),
        now_ms=NOW,
    )

    assert result.snapshot.valid is True
    assert result.attested_dispatch is not None
    assert result.attested_dispatch.valid is True
    assert result.valid is True


def test_layered_verification_binds_dispatch_to_verified_snapshot_copy(monkeypatch):
    fixture = fixture_data()
    snapshot = copy.deepcopy(fixture["base_snapshot"])
    attestation_fixture = json.loads(
        ATTESTATION_FIXTURE.read_text(encoding="utf-8")
    )
    original_verify = verify_trust_root_snapshot

    def verify_then_mutate_external_snapshot(*args, **kwargs):
        result = original_verify(*args, **kwargs)
        snapshot["trust_root"]["keys"][0]["revoked"] = True
        return result

    monkeypatch.setattr(
        trust_snapshot_module,
        "verify_trust_root_snapshot",
        verify_then_mutate_external_snapshot,
    )
    result = verify_attested_dispatch_with_snapshot(
        snapshot,
        copy.deepcopy(fixture["bootstrap_authority"]),
        copy.deepcopy(fixture["base_checkpoint"]),
        copy.deepcopy(attestation_fixture["base_envelope"]),
        now_ms=NOW,
    )

    assert snapshot["trust_root"]["keys"][0]["revoked"] is True
    assert result.snapshot.valid is True
    assert result.attested_dispatch is not None
    assert result.attested_dispatch.valid is True
    assert result.valid is True
