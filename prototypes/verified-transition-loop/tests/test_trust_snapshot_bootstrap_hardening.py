import copy
from pathlib import Path

from verified_transition_loop.trust_snapshot import (
    load_fixture,
    verify_trust_root_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "trust-root-snapshot-v0.9.json"
NOW = 1_800_000_001_000


def base_inputs():
    fixture = load_fixture(FIXTURE)
    return (
        copy.deepcopy(fixture["base_snapshot"]),
        copy.deepcopy(fixture["bootstrap_authority"]),
        copy.deepcopy(fixture["base_checkpoint"]),
    )


def test_duplicate_bootstrap_key_id_fails_closed_regardless_of_order():
    snapshot, bootstrap, checkpoint = base_inputs()
    duplicate = copy.deepcopy(bootstrap["keys"][0])
    duplicate["public_key_base64"] = "gTl3Dqh9F19Wo1Rmw0x+zMuNipG07jeiXfYPW4/Js5Q="
    bootstrap["keys"].append(duplicate)

    result = verify_trust_root_snapshot(
        snapshot, bootstrap, checkpoint, now_ms=NOW
    )
    assert result.valid is False
    assert result.bootstrap_signature_valid is False
    assert result.bootstrap_authority_valid is False
    assert result.reason_codes == ("BOOTSTRAP_KEY_AMBIGUOUS",)

    bootstrap["keys"].reverse()
    reversed_result = verify_trust_root_snapshot(
        snapshot, bootstrap, checkpoint, now_ms=NOW
    )
    assert reversed_result.valid is False
    assert reversed_result.reason_codes == ("BOOTSTRAP_KEY_AMBIGUOUS",)


def test_malformed_bootstrap_public_key_is_authority_failure():
    snapshot, bootstrap, checkpoint = base_inputs()
    bootstrap["keys"][0]["public_key_base64"] = "not-base64!"

    result = verify_trust_root_snapshot(
        snapshot, bootstrap, checkpoint, now_ms=NOW
    )
    assert result.valid is False
    assert result.bootstrap_signature_valid is False
    assert result.bootstrap_authority_valid is False
    assert result.reason_codes == ("BOOTSTRAP_KEY_MATERIAL_INVALID",)


def test_wrong_length_bootstrap_public_key_is_authority_failure():
    snapshot, bootstrap, checkpoint = base_inputs()
    bootstrap["keys"][0]["public_key_base64"] = "AA=="

    result = verify_trust_root_snapshot(
        snapshot, bootstrap, checkpoint, now_ms=NOW
    )
    assert result.valid is False
    assert result.bootstrap_signature_valid is False
    assert result.bootstrap_authority_valid is False
    assert result.reason_codes == ("BOOTSTRAP_KEY_MATERIAL_INVALID",)


def test_inverted_bootstrap_key_interval_fails_closed():
    snapshot, bootstrap, checkpoint = base_inputs()
    key = bootstrap["keys"][0]
    key["not_before_ms"] = NOW + 1000
    key["not_after_ms"] = NOW - 1000

    result = verify_trust_root_snapshot(
        snapshot, bootstrap, checkpoint, now_ms=NOW
    )
    assert result.valid is False
    assert result.bootstrap_signature_valid is True
    assert result.bootstrap_authority_valid is False
    assert result.reason_codes == ("BOOTSTRAP_KEY_VALIDITY_INVALID",)


def test_checkpoint_from_future_is_freshness_failure_only():
    snapshot, bootstrap, checkpoint = base_inputs()
    checkpoint["checkpointed_at_ms"] = NOW + 1

    result = verify_trust_root_snapshot(
        snapshot, bootstrap, checkpoint, now_ms=NOW
    )
    assert result.valid is False
    assert result.snapshot_integrity_valid is True
    assert result.bootstrap_signature_valid is True
    assert result.bootstrap_authority_valid is True
    assert result.freshness_valid is False
    assert result.continuity_valid is True
    assert result.reason_codes == ("CHECKPOINT_FROM_FUTURE",)


def test_checkpoint_known_state_must_be_complete_pair():
    snapshot, bootstrap, checkpoint = base_inputs()
    checkpoint["known_snapshot_digest"] = None

    result = verify_trust_root_snapshot(
        snapshot, bootstrap, checkpoint, now_ms=NOW
    )
    assert result.valid is False
    assert result.snapshot_integrity_valid is False
    assert result.bootstrap_signature_valid is False
    assert result.bootstrap_authority_valid is False
    assert result.freshness_valid is False
    assert result.continuity_valid is False
    assert result.reason_codes == ("CHECKPOINT_KNOWN_STATE_INCOMPLETE",)
