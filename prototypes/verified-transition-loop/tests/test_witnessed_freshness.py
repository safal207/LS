from __future__ import annotations

import copy
from pathlib import Path

from verified_transition_loop.witnessed_freshness import (
    CANONICAL_PROFILE,
    compute_witness_statement_id,
    verify_witnessed_freshness,
)
from verified_transition_loop.witnessed_freshness_conformance import load_fixture, run_fixture

FIXTURE = Path(__file__).parents[1] / "fixtures" / "witnessed-freshness-v0.13.json"


def test_all_witnessed_freshness_vectors_pass() -> None:
    result = run_fixture(load_fixture(FIXTURE))
    assert result["summary"] == {"total": 20, "passed": 20, "failed": 0, "all_passed": True}


def test_split_view_blocks_even_when_target_quorum_is_satisfied() -> None:
    result = run_fixture(load_fixture(FIXTURE))
    case = next(item for item in result["cases"] if item["id"] == "split-view-blocks-even-with-target-quorum")
    assert case["actual"]["witness_quorum_valid"] is True
    assert case["actual"]["equivocation_detected"] is True
    assert case["actual"]["view_consistency_valid"] is False
    assert case["actual"]["valid"] is False


def test_duplicate_witness_identity_does_not_inflate_quorum() -> None:
    result = run_fixture(load_fixture(FIXTURE))
    case = next(item for item in result["cases"] if item["id"] == "duplicate-witness-does-not-count-twice")
    assert case["actual"]["accepted_witness_ids"] == ["witness-a"]
    assert case["actual"]["witness_quorum_valid"] is False


def test_valid_witnesses_cannot_rescue_invalid_v012_snapshot() -> None:
    result = run_fixture(load_fixture(FIXTURE))
    case = next(item for item in result["cases"] if item["id"] == "local-v012-failure-not-rescued")
    assert case["actual"]["witness_quorum_valid"] is True
    assert case["actual"]["local_snapshot_valid"] is False
    assert case["actual"]["valid"] is False
    assert case["actual"]["reason_codes"] == ["LOCAL_SNAPSHOT_INVALID"]


def test_statement_identity_is_canonical_and_version_bound() -> None:
    fixture = load_fixture(FIXTURE)
    statement = fixture["statements"]["a_target"]
    assert statement["canonical_profile"] == CANONICAL_PROFILE
    assert compute_witness_statement_id(statement) == statement["statement_id"]


def test_revocation_preserves_math_signature_but_removes_authority() -> None:
    fixture = load_fixture(FIXTURE)
    authority = copy.deepcopy(fixture["witness_authority"])
    authority["keys"][1]["revoked"] = True
    result = verify_witnessed_freshness(
        snapshot_view=fixture["snapshot_view"],
        local_snapshot_valid=True,
        witness_statements=[fixture["statements"]["a_target"], fixture["statements"]["b_target"]],
        witness_authority=authority,
        now_ms=fixture["base_now_ms"],
    )
    assert result.witness_signature_valid is True
    assert result.witness_authority_valid is False
    assert result.valid is False


def test_conformance_is_deterministic() -> None:
    fixture = load_fixture(FIXTURE)
    assert run_fixture(fixture) == run_fixture(fixture)
