from __future__ import annotations

import copy
from pathlib import Path

from verified_transition_loop.canonical import MAX_SAFE_INTEGER, strict_loads
from verified_transition_loop.canonical_trust_snapshot import (
    CANONICAL_PROFILE,
    verify_canonical_trust_snapshot,
)
from verified_transition_loop.canonical_trust_snapshot_conformance import run_fixture

FIXTURE = Path(__file__).parents[1] / "fixtures" / "canonical-trust-root-snapshot-v0.12.json"


def _fixture() -> dict:
    return strict_loads(FIXTURE.read_text(encoding="utf-8"))


def _variant(fixture: dict, name: str) -> dict:
    snapshot = copy.deepcopy(fixture["base_snapshot"])
    snapshot.update(copy.deepcopy(fixture["snapshot_variants"][name]))
    return snapshot


def test_machine_readable_fixture_passes() -> None:
    result = run_fixture(_fixture())
    assert result["canonical_profile"] == CANONICAL_PROFILE
    assert result["summary"] == {
        "total": 20,
        "passed": 20,
        "failed": 0,
        "all_passed": True,
    }
    assert result["parity"]["signed_payload_matches_expected"] is True
    assert result["parity"]["signature_matches_expected"] is True
    assert result["parity"]["snapshot_digest_matches_expected"] is True


def test_fresh_snapshot_verifies_exact_signed_bytes_and_digest() -> None:
    fixture = _fixture()
    result = verify_canonical_trust_snapshot(
        copy.deepcopy(fixture["base_snapshot"]),
        copy.deepcopy(fixture["bootstrap_authority"]),
        copy.deepcopy(fixture["checkpoints"]["base"]),
        now_ms=fixture["base_now_ms"],
    )
    assert result.valid is True
    assert result.bootstrap_signature_valid is True
    assert result.signed_payload_base64 == fixture["expected_fresh_signed_payload_base64"]
    assert result.snapshot_digest == fixture["expected_fresh_snapshot_digest"]


def test_historically_signed_snapshot_cannot_roll_back_checkpoint() -> None:
    fixture = _fixture()
    result = verify_canonical_trust_snapshot(
        _variant(fixture, "historical"),
        copy.deepcopy(fixture["bootstrap_authority"]),
        copy.deepcopy(fixture["checkpoints"]["known_gen2"]),
        now_ms=fixture["base_now_ms"],
    )
    assert result.bootstrap_signature_valid is True
    assert result.freshness_valid is True
    assert result.continuity_valid is False
    assert result.reason_codes == ("SNAPSHOT_ROLLBACK",)
    assert result.valid is False


def test_validly_signed_same_generation_fork_is_rejected() -> None:
    fixture = _fixture()
    result = verify_canonical_trust_snapshot(
        _variant(fixture, "fork"),
        copy.deepcopy(fixture["bootstrap_authority"]),
        copy.deepcopy(fixture["checkpoints"]["base"]),
        now_ms=fixture["base_now_ms"],
    )
    assert result.bootstrap_signature_valid is True
    assert result.snapshot_integrity_valid is True
    assert result.continuity_valid is False
    assert result.reason_codes == ("SNAPSHOT_FORK_DETECTED",)


def test_wrong_canonical_profile_can_be_signed_but_is_not_accepted() -> None:
    fixture = _fixture()
    result = verify_canonical_trust_snapshot(
        _variant(fixture, "bad_profile"),
        copy.deepcopy(fixture["bootstrap_authority"]),
        copy.deepcopy(fixture["checkpoints"]["base"]),
        now_ms=fixture["base_now_ms"],
    )
    assert result.bootstrap_signature_valid is True
    assert result.canonical_profile_valid is False
    assert result.snapshot_integrity_valid is False
    assert result.reason_codes == ("CANONICAL_PROFILE_MISMATCH",)
    assert result.valid is False


def test_root_payload_tamper_does_not_invalidate_historical_signature_but_fails_integrity() -> None:
    fixture = _fixture()
    snapshot = copy.deepcopy(fixture["base_snapshot"])
    snapshot["trust_root"]["keys"][0]["revoked"] = True
    result = verify_canonical_trust_snapshot(
        snapshot,
        copy.deepcopy(fixture["bootstrap_authority"]),
        copy.deepcopy(fixture["checkpoints"]["base"]),
        now_ms=fixture["base_now_ms"],
    )
    assert result.bootstrap_signature_valid is True
    assert result.snapshot_integrity_valid is False
    assert result.reason_codes == ("TRUST_ROOT_DIGEST_MISMATCH",)
    assert result.valid is False


def test_incomplete_checkpoint_fails_before_trust_claims() -> None:
    fixture = _fixture()
    checkpoint = copy.deepcopy(fixture["checkpoints"]["base"])
    checkpoint["known_generation"] = None
    result = verify_canonical_trust_snapshot(
        copy.deepcopy(fixture["base_snapshot"]),
        copy.deepcopy(fixture["bootstrap_authority"]),
        checkpoint,
        now_ms=fixture["base_now_ms"],
    )
    assert result.valid is False
    assert result.snapshot_integrity_valid is False
    assert result.bootstrap_signature_valid is False
    assert result.reason_codes == ("CHECKPOINT_KNOWN_STATE_INCOMPLETE",)


def test_unsafe_generation_fails_closed() -> None:
    fixture = _fixture()
    snapshot = copy.deepcopy(fixture["base_snapshot"])
    snapshot["generation"] = MAX_SAFE_INTEGER + 1
    result = verify_canonical_trust_snapshot(
        snapshot,
        copy.deepcopy(fixture["bootstrap_authority"]),
        copy.deepcopy(fixture["checkpoints"]["base"]),
        now_ms=fixture["base_now_ms"],
    )
    assert result.valid is False
    assert result.reason_codes == ("SNAPSHOT_SCHEMA_INVALID:generation",)
