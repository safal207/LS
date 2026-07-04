from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from validate_levels import LevelOverlayError, validate_level_overlay  # noqa: E402

TRAIL_FIXTURE = ROOT / "fixtures" / "robys_pr_164_wordmark.json"
OVERLAY_FIXTURE = ROOT / "fixtures" / "robys_pr_164_levels.json"


class CausalLevelOverlayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.trail = json.loads(TRAIL_FIXTURE.read_text(encoding="utf-8"))
        self.overlay = json.loads(OVERLAY_FIXTURE.read_text(encoding="utf-8"))

    def assert_invalid(self, overlay: dict, message: str) -> None:
        with self.assertRaisesRegex(LevelOverlayError, message):
            validate_level_overlay(self.trail, overlay)

    def interaction(self, overlay: dict, interaction_id: str) -> dict:
        return next(item for item in overlay["interactions"] if item["id"] == interaction_id)

    def test_real_overlay_is_valid(self) -> None:
        validate_level_overlay(self.trail, self.overlay)
        self.assertEqual(
            set(item["level"] for item in self.overlay["assignments"]),
            {"INDIVIDUAL", "SYSTEM", "ENVIRONMENT"},
        )

    def test_every_trail_node_requires_one_assignment(self) -> None:
        overlay = copy.deepcopy(self.overlay)
        overlay["assignments"] = overlay["assignments"][:-1]
        self.assert_invalid(overlay, "every trail node must have a causal level")

    def test_duplicate_assignment_is_rejected(self) -> None:
        overlay = copy.deepcopy(self.overlay)
        overlay["assignments"].append(copy.deepcopy(overlay["assignments"][0]))
        self.assert_invalid(overlay, "duplicate level assignment")

    def test_interaction_level_must_match_node_assignment(self) -> None:
        overlay = copy.deepcopy(self.overlay)
        self.interaction(overlay, "interaction.individual-detects-system-risk")["fromLevel"] = "SYSTEM"
        self.assert_invalid(overlay, "fromLevel disagrees with assignment")

    def test_interaction_mode_is_derived_from_levels(self) -> None:
        overlay = copy.deepcopy(self.overlay)
        self.interaction(overlay, "interaction.system-blocks-system-transition")["mode"] = "CROSS_LEVEL"
        self.assert_invalid(overlay, "mode does not match its levels")

    def test_edge_bound_interaction_must_match_edge_endpoints(self) -> None:
        overlay = copy.deepcopy(self.overlay)
        self.interaction(overlay, "interaction.system-exposes-environment-risk")["toNodeId"] = "state.current-risk-discovered"
        self.interaction(overlay, "interaction.system-exposes-environment-risk")["toLevel"] = "SYSTEM"
        self.assert_invalid(overlay, "toNodeId disagrees with edge")

    def test_derived_interaction_needs_multiple_evidence_nodes(self) -> None:
        overlay = copy.deepcopy(self.overlay)
        self.interaction(overlay, "interaction.environment-constrains-system-phase")["evidenceNodeIds"] = [
            "cause.legacy-parser-rejection"
        ]
        self.assert_invalid(overlay, "without edgeId needs at least two evidence nodes")

    def test_exact_head_binding_is_required(self) -> None:
        overlay = copy.deepcopy(self.overlay)
        overlay["trailRef"]["currentHead"] = self.trail["subject"]["baseHead"]
        self.assert_invalid(overlay, "trailRef.currentHead does not match trail currentHead")

    def test_feedback_loop_requires_all_directed_pairs(self) -> None:
        overlay = copy.deepcopy(self.overlay)
        overlay["interactions"] = [
            item
            for item in overlay["interactions"]
            if item["id"] != "interaction.environment-constrains-system-phase"
        ]
        self.assert_invalid(overlay, "level interaction loop is incomplete")

    def test_dominant_loop_must_close(self) -> None:
        overlay = copy.deepcopy(self.overlay)
        overlay["summary"]["dominantLoop"][-1] = "SYSTEM"
        self.assert_invalid(overlay, "dominantLoop must return to its starting level")


if __name__ == "__main__":
    unittest.main()
