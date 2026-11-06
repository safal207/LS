"""Non-normative regressions for LGD-Eval's 2026-10-17 VTL v0.14 review.

Tests intentionally do not change the v0.14 fixture or result contract.
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from verified_transition_loop.transparency_log_strict import (
    verify_transparency_log,
)

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "fixtures" / "transparency-log-v0.14.json"
NODE_STRICT = ROOT / "reference" / "transparency-log-strict-v0.14.mjs"


def _fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _node_result(
    bundle: dict[str, Any], now_ms: int, tmp_path: Path
) -> dict[str, Any]:
    input_path = tmp_path / "lgd-eval-v014-bundle.json"
    input_path.write_text(json.dumps(bundle), encoding="utf-8")
    node = shutil.which("node")
    assert node is not None, (
        "Node.js is required for VTL Python/Node parity tests; "
        "install Node.js and ensure node is on PATH"
    )
    proc = subprocess.run(
        [node, str(NODE_STRICT), str(input_path), str(now_ms)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode in (0, 1), proc.stderr
    actual = json.loads(proc.stdout)
    assert proc.returncode == (0 if actual["valid"] else 1)
    return actual


def _verify_both(
    bundle: dict[str, Any], now_ms: int, tmp_path: Path
) -> dict[str, Any]:
    python_result = asdict(verify_transparency_log(bundle, now_ms=now_ms))
    python_result["reason_codes"] = list(python_result["reason_codes"])
    node_result = _node_result(bundle, now_ms, tmp_path)
    assert python_result == node_result
    return node_result


def _consumer_checkpoint(
    trusted_anchor: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    """Test-only caller policy: promote only a fully accepted checkpoint."""
    if not result["valid"]:
        return copy.deepcopy(trusted_anchor)
    assert result["accepted_tree_size"] is not None
    assert result["accepted_root_hash"] is not None
    return {
        "tree_size": result["accepted_tree_size"],
        "root_hash": result["accepted_root_hash"],
    }


def _tamper_digest(bundle: dict[str, Any]) -> None:
    original = bundle["entry"]["snapshot_digest"]
    bundle["entry"]["snapshot_digest"] = (
        ("0" if original[0] != "0" else "1") + original[1:]
    )


def test_missing_evidence_and_conflicting_evidence_remain_distinguishable(
    tmp_path: Path,
) -> None:
    """F1: existing reason codes distinguish the cases, although valid is binary."""
    fixture = _fixture()
    missing = copy.deepcopy(fixture["base_bundle"])
    missing.pop("inclusion_path")
    wrong = copy.deepcopy(fixture["base_bundle"])
    _tamper_digest(wrong)

    missing_result = _verify_both(missing, fixture["base_now_ms"], tmp_path)
    wrong_result = _verify_both(wrong, fixture["base_now_ms"], tmp_path)

    assert missing_result["valid"] is False
    assert wrong_result["valid"] is False
    assert "TRANSPARENCY_BUNDLE_FIELDS_INVALID" in missing_result["reason_codes"]
    assert "ENTRY_SNAPSHOT_DIGEST_MISMATCH" in wrong_result["reason_codes"]
    assert "ENTRY_SNAPSHOT_DIGEST_MISMATCH" not in missing_result["reason_codes"]
    assert "TRANSPARENCY_BUNDLE_FIELDS_INVALID" not in wrong_result["reason_codes"]
    assert "INCLUSION_PROOF_INVALID" in missing_result["reason_codes"]
    assert "INCLUSION_PROOF_INVALID" in wrong_result["reason_codes"]


@pytest.mark.parametrize("variant", ("missing_inclusion", "tampered_digest"))
def test_rejection_never_promotes_candidate_over_prior_trusted_anchor(
    variant: str, tmp_path: Path
) -> None:
    """F2: accepted_* names a newly accepted candidate, not retained prior state."""
    fixture = _fixture()
    bundle = copy.deepcopy(fixture["base_bundle"])
    prior = copy.deepcopy(bundle["verifier_checkpoint"])
    # Minimal test-only consumer: the trusted anchor lives outside the bundle.
    trusted_anchor = {
        "tree_size": prior["known_tree_size"],
        "root_hash": prior["known_root_hash"],
    }
    now_ms = fixture["base_now_ms"]

    good = _verify_both(bundle, now_ms, tmp_path)
    assert good["valid"] is True
    assert good["accepted_tree_size"] == bundle["checkpoint"]["tree_size"]
    assert good["accepted_root_hash"] == bundle["checkpoint"]["root_hash"]
    promoted = _consumer_checkpoint(trusted_anchor, good)
    assert promoted == {
        "tree_size": bundle["checkpoint"]["tree_size"],
        "root_hash": bundle["checkpoint"]["root_hash"],
    }
    assert promoted != trusted_anchor

    if variant == "missing_inclusion":
        bundle.pop("inclusion_path")
    else:
        _tamper_digest(bundle)
    rejected = _verify_both(bundle, now_ms, tmp_path)
    assert rejected["valid"] is False
    assert rejected["accepted_tree_size"] is None
    assert rejected["accepted_root_hash"] is None

    # The independent prior checkpoint is retained after a rejected candidate.
    retained = _consumer_checkpoint(trusted_anchor, rejected)
    assert retained == {
        "tree_size": prior["known_tree_size"],
        "root_hash": prior["known_root_hash"],
    }
    assert retained != promoted
    assert bundle["verifier_checkpoint"] == prior


def test_valid_other_layers_cannot_rescue_checkpoint_structure(
    tmp_path: Path,
) -> None:
    """F3: an unsigned extra field invalidates structure, not signature math."""
    fixture = _fixture()
    bundle = copy.deepcopy(fixture["base_bundle"])
    bundle["checkpoint"]["unpublished_comment"] = "not in v0.14 contract"
    actual = _verify_both(bundle, fixture["base_now_ms"], tmp_path)

    assert actual["valid"] is False
    assert actual["log_checkpoint_integrity_valid"] is False
    assert "CHECKPOINT_FIELDS_INVALID" in actual["reason_codes"]
    assert actual["log_checkpoint_signature_valid"] is True
    assert actual["inclusion_valid"] is True
    assert actual["consistency_valid"] is True
    assert actual["accepted_tree_size"] is None
    assert actual["accepted_root_hash"] is None
