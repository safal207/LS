from __future__ import annotations

import copy
import json
from pathlib import Path

from verified_transition_loop.transparency_log import (
    merkle_leaf_hash,
    verify_consistency_proof,
    verify_inclusion_proof,
    verify_transparency_log,
)
from verified_transition_loop.transparency_log_conformance import run_fixture

FIXTURE = Path(__file__).parents[1] / "fixtures" / "transparency-log-v0.14.json"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_v014_fixture_all_25_vectors_pass() -> None:
    result = run_fixture(_fixture())
    failed = [case["id"] for case in result["cases"] if not case["passed"]]
    false_parity = [
        key
        for key, value in result["parity"].items()
        if key.endswith("_matches_expected") and value is not True
    ]
    diagnostics = {"failed_cases": failed, "false_parity": false_parity}
    assert result["summary"] == {
        "total": 25,
        "passed": 25,
        "failed": 0,
        "all_passed": True,
    }, diagnostics


def test_rfc6962_style_leaf_hash_matches_fixture() -> None:
    fixture = _fixture()
    assert merkle_leaf_hash(fixture["base_bundle"]["entry"]) == fixture["expected_base_leaf_hash"]


def test_inclusion_proof_accepts_target_leaf() -> None:
    fixture = _fixture()
    bundle = fixture["base_bundle"]
    assert verify_inclusion_proof(
        leaf_index=bundle["leaf_index"],
        tree_size=bundle["checkpoint"]["tree_size"],
        leaf_hash=merkle_leaf_hash(bundle["entry"]),
        root_hash=bundle["checkpoint"]["root_hash"],
        audit_path=bundle["inclusion_path"],
    )


def test_inclusion_proof_rejects_tampered_path() -> None:
    fixture = _fixture()
    bundle = fixture["base_bundle"]
    path = copy.deepcopy(bundle["inclusion_path"])
    path[0] = "00" * 32
    assert not verify_inclusion_proof(
        leaf_index=bundle["leaf_index"],
        tree_size=bundle["checkpoint"]["tree_size"],
        leaf_hash=merkle_leaf_hash(bundle["entry"]),
        root_hash=bundle["checkpoint"]["root_hash"],
        audit_path=path,
    )


def test_consistency_proof_accepts_append_only_extension() -> None:
    fixture = _fixture()
    bundle = fixture["base_bundle"]
    previous = bundle["verifier_checkpoint"]
    current = bundle["checkpoint"]
    assert verify_consistency_proof(
        old_size=previous["known_tree_size"],
        new_size=current["tree_size"],
        old_root_hash=previous["known_root_hash"],
        new_root_hash=current["root_hash"],
        proof=bundle["consistency_path"],
    )


def test_consistency_proof_rejects_mutation() -> None:
    fixture = _fixture()
    bundle = fixture["base_bundle"]
    previous = bundle["verifier_checkpoint"]
    current = bundle["checkpoint"]
    proof = copy.deepcopy(bundle["consistency_path"])
    proof[0] = "00" * 32
    assert not verify_consistency_proof(
        old_size=previous["known_tree_size"],
        new_size=current["tree_size"],
        old_root_hash=previous["known_root_hash"],
        new_root_hash=current["root_hash"],
        proof=proof,
    )


def test_valid_peer_split_view_blocks_even_with_valid_inclusion_and_consistency() -> None:
    fixture = _fixture()
    bundle = copy.deepcopy(fixture["base_bundle"])
    bundle["peer_checkpoints"] = [copy.deepcopy(fixture["checkpoint_variants"]["conflict"])]
    result = verify_transparency_log(bundle, now_ms=fixture["base_now_ms"])
    assert result.inclusion_valid is True
    assert result.consistency_valid is True
    assert result.log_equivocation_detected is True
    assert result.view_consistency_valid is False
    assert result.valid is False


def test_valid_log_proof_cannot_rescue_invalid_v013_witness_layer() -> None:
    fixture = _fixture()
    bundle = copy.deepcopy(fixture["base_bundle"])
    bundle["local_witnessed_freshness_valid"] = False
    result = verify_transparency_log(bundle, now_ms=fixture["base_now_ms"])
    assert result.inclusion_valid is True
    assert result.consistency_valid is True
    assert result.local_witnessed_freshness_valid is False
    assert result.valid is False
