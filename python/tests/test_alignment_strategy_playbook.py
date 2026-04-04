# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modules"))

from modules.agent.alignment_strategy_playbook import (
    AlignmentStrategyPlaybookMetrics,
    build_alignment_strategy_playbook,
)


class TestAlignmentStrategyPlaybook(unittest.TestCase):
    def test_empty_recommendations(self) -> None:
        out = build_alignment_strategy_playbook([])
        self.assertEqual(out["selected_strategy_ids"], [])
        self.assertEqual(out["confidence"], 0.0)

    def test_expected_top_level_keys(self) -> None:
        recs = [{"strategy_id": "s1", "effective_rate": 0.8, "support_count": 3, "recommended_actions": ["acknowledge common ground before moving forward"]}]
        out = build_alignment_strategy_playbook(recs)
        self.assertEqual(
            set(out.keys()),
            {
                "current_playbook_id",
                "selected_strategy_ids",
                "why_selected",
                "confidence",
                "risk_notes",
                "steps",
            },
        )

    def test_phase_order_respected(self) -> None:
        recs = [{
            "strategy_id": "s1",
            "effective_rate": 0.8,
            "support_count": 4,
            "recommended_actions": [
                "frame solutions as shared options, not unilateral decisions",
                "synchronize positions before suggesting action",
                "acknowledge common ground before moving forward",
            ],
        }]
        out = build_alignment_strategy_playbook(recs)
        phases = [s["phase"] for s in out["steps"]]
        self.assertEqual(phases, ["acknowledge_tension", "synchronize_positions", "co_create_solution"])

    def test_hotspot_reflected_in_reason_and_risk(self) -> None:
        recs = [{"strategy_id": "s1", "effective_rate": 0.7, "support_count": 2, "recommended_actions": ["acknowledge common ground before moving forward"]}]
        report = {"pairwise_hotspots": [{"tension_axis": "trust"}]}
        out = build_alignment_strategy_playbook(recs, alignment_report=report)
        self.assertIn("trust", out["why_selected"])
        self.assertTrue(any("trust" in note for note in out["risk_notes"]))

    def test_calibration_risks_attached(self) -> None:
        recs = [{"strategy_id": "s1", "effective_rate": 0.5, "support_count": 1, "recommended_actions": ["invite the other party to respond before concluding"]}]
        calibration = {"overview": {"recommended_but_not_adopted_total": 1, "adopted_but_low_outcome_total": 1}}
        out = build_alignment_strategy_playbook(recs, calibration_summary=calibration)
        notes = " ".join(out["risk_notes"])
        self.assertIn("adoption gap", notes)
        self.assertIn("outcome risk", notes)


class TestPlaybookMetrics(unittest.TestCase):
    def test_metrics_to_dict(self) -> None:
        m = AlignmentStrategyPlaybookMetrics(calls_total=2, nonempty_total=1, strategies_selected_total=3)
        d = m.to_dict()
        self.assertEqual(d["calls_total"], 2)
        self.assertEqual(d["avg_selected_per_nonempty"], 3.0)


if __name__ == "__main__":
    unittest.main()
