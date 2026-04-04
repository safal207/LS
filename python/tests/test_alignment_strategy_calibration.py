# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modules"))

from modules.agent.alignment_strategy_calibration import (
    AlignmentStrategyCalibrationMetrics,
    _build_calibration_reason,
    build_per_strategy_calibration_stats,
    build_strategy_calibration_summary,
)
from modules.agent.resonance_agent import ResonanceAgent


class TestCalibrationBuilder(unittest.TestCase):
    def test_empty_inputs_return_empty_summary(self) -> None:
        out = build_strategy_calibration_summary([], [], [], {})
        self.assertEqual(out["overview"]["total_strategies_seen"], 0)
        self.assertEqual(out["per_strategy"], [])

    def test_well_calibrated_label(self) -> None:
        recs = [{"strategy_id": "s1"}] * 4
        adp = [{"strategy_id": "s1", "adoption_label": "adopted", "adoption_score": 1.0}] * 4
        fb = [{"strategy_id": "s1", "feedback_label": "effective", "response_score": 0.9, "goal_alignment_score": 0.8}] * 4
        row = build_strategy_calibration_summary(recs, fb, adp, {})["per_strategy"][0]
        self.assertEqual(row["calibration_label"], "well_calibrated")

    def test_promising_but_thin_label(self) -> None:
        recs = [{"strategy_id": "s1"}]
        adp = [{"strategy_id": "s1", "adoption_label": "adopted", "adoption_score": 0.8}]
        fb = [{"strategy_id": "s1", "feedback_label": "effective", "response_score": 0.7, "goal_alignment_score": 0.7}]
        row = build_strategy_calibration_summary(recs, fb, adp, {})["per_strategy"][0]
        self.assertEqual(row["calibration_label"], "promising_but_thin")

    def test_recommended_but_not_adopted_label(self) -> None:
        recs = [{"strategy_id": "s1"}] * 5
        adp = [{"strategy_id": "s1", "adoption_label": "not_adopted", "adoption_score": 0.0}] * 5
        row = build_strategy_calibration_summary(recs, [], adp, {})["per_strategy"][0]
        self.assertEqual(row["calibration_label"], "recommended_but_not_adopted")

    def test_adopted_but_low_outcome_label(self) -> None:
        recs = [{"strategy_id": "s1"}] * 3
        adp = [{"strategy_id": "s1", "adoption_label": "adopted", "adoption_score": 0.9}] * 3
        fb = [{"strategy_id": "s1", "feedback_label": "ineffective", "response_score": 0.2, "goal_alignment_score": 0.2}] * 3
        row = build_strategy_calibration_summary(recs, fb, adp, {})["per_strategy"][0]
        self.assertEqual(row["calibration_label"], "adopted_but_low_outcome")

    def test_weakly_calibrated_label(self) -> None:
        recs = [{"strategy_id": "s1"}] * 2
        adp = [{"strategy_id": "s1", "adoption_label": "not_adopted", "adoption_score": 0.0}] * 2
        fb = [{"strategy_id": "s1", "feedback_label": "ineffective", "response_score": 0.2, "goal_alignment_score": 0.2}] * 2
        row = build_strategy_calibration_summary(recs, fb, adp, {})["per_strategy"][0]
        self.assertEqual(row["calibration_label"], "weakly_calibrated")

    def test_insufficient_data_label(self) -> None:
        recs = [{"strategy_id": "s1"}]
        row = build_strategy_calibration_summary(recs, [], [], {})["per_strategy"][0]
        self.assertEqual(row["calibration_label"], "insufficient_data")

    def test_aggregate_values(self) -> None:
        recs = [{"strategy_id": "s1", "based_on_pattern_ids": ["p1"]}] * 3
        adp = [
            {"strategy_id": "s1", "adoption_label": "adopted", "adoption_score": 1.0},
            {"strategy_id": "s1", "adoption_label": "partially_adopted", "adoption_score": 0.5},
            {"strategy_id": "s1", "adoption_label": "not_adopted", "adoption_score": 0.0},
        ]
        fb = [
            {"strategy_id": "s1", "feedback_label": "effective", "response_score": 0.9, "goal_alignment_score": 0.8, "pattern_ids": ["p1"]},
            {"strategy_id": "s1", "feedback_label": "neutral", "response_score": 0.4, "goal_alignment_score": 0.5, "pattern_ids": ["p2"]},
            {"strategy_id": "s1", "feedback_label": "ineffective", "response_score": 0.2, "goal_alignment_score": 0.2, "pattern_ids": ["p2"]},
        ]
        row = build_strategy_calibration_summary(recs, fb, adp, {})["per_strategy"][0]
        self.assertEqual(row["times_recommended"], 3)
        self.assertEqual(row["times_adopted"], 1)
        self.assertEqual(row["times_partially_adopted"], 1)
        self.assertEqual(row["times_not_adopted"], 1)
        self.assertAlmostEqual(row["adoption_rate"], 0.5, places=4)
        self.assertAlmostEqual(row["effective_rate"], 1 / 3, places=4)
        self.assertAlmostEqual(row["avg_adoption_score"], 0.5, places=4)
        self.assertAlmostEqual(row["avg_response_score"], 0.5, places=4)
        self.assertAlmostEqual(row["avg_goal_alignment_score"], 0.5, places=4)
        self.assertEqual(set(row.keys()), {
            "strategy_id", "times_recommended", "times_adopted", "times_partially_adopted",
            "times_not_adopted", "adoption_rate", "effective_total", "neutral_total",
            "ineffective_total", "effective_rate", "avg_adoption_score", "avg_response_score",
            "avg_goal_alignment_score", "reputation_label", "calibration_label",
            "calibration_reason", "linked_pattern_ids_top",
        })

    def test_reason_deterministic_and_explainable(self) -> None:
        stats = {"calibration_label": "recommended_but_not_adopted"}
        self.assertEqual(_build_calibration_reason(stats), _build_calibration_reason(stats))
        self.assertIn("recommended", _build_calibration_reason(stats))

    def test_top_lists_limited_and_serializable(self) -> None:
        recs = [{"strategy_id": f"s{i}"} for i in range(8)]
        out = build_strategy_calibration_summary(recs, [], [], {}, top_k=3)
        self.assertLessEqual(len(out["overview"]["top_well_calibrated_strategies"]), 3)
        self.assertLessEqual(len(out["overview"]["top_underadopted_strategies"]), 3)
        self.assertLessEqual(len(out["overview"]["top_low_outcome_strategies"]), 3)
        import json

        json.dumps(out)


    def test_aggregation_strategy_stats_list_shape_supported(self) -> None:
        agg = {"strategy_stats": [{"strategy_id": "s1", "reputation_label": "stable"}]}
        row = build_strategy_calibration_summary([{"strategy_id": "s1"}], [], [], agg)["per_strategy"][0]
        self.assertEqual(row["reputation_label"], "stable")

    def test_ineffective_feedback_counts_as_evidence(self) -> None:
        recs = [{"strategy_id": "s1"}]
        fb = [{"strategy_id": "s1", "feedback_label": "ineffective", "response_score": 0.2, "goal_alignment_score": 0.2}]
        row = build_strategy_calibration_summary(recs, fb, [], {})["per_strategy"][0]
        self.assertNotEqual(row["calibration_label"], "insufficient_data")

    def test_no_mutation_of_inputs(self) -> None:
        recs = [{"strategy_id": "s1"}]
        fb = [{"strategy_id": "s1", "feedback_label": "neutral"}]
        adp = [{"strategy_id": "s1", "adoption_label": "not_adopted"}]
        agg = {"strategy_stats": {"s1": {"reputation_label": "stable"}}}
        before = (copy.deepcopy(recs), copy.deepcopy(fb), copy.deepcopy(adp), copy.deepcopy(agg))
        _ = build_strategy_calibration_summary(recs, fb, adp, agg)
        self.assertEqual(before[0], recs)
        self.assertEqual(before[1], fb)
        self.assertEqual(before[2], adp)
        self.assertEqual(before[3], agg)


class TestMetrics(unittest.TestCase):
    def test_metrics_to_dict(self) -> None:
        m = AlignmentStrategyCalibrationMetrics(calls_total=2, strategies_processed_total=6)
        d = m.to_dict()
        self.assertEqual(d["calls_total"], 2)
        self.assertEqual(d["strategies_processed_total"], 6)


class TestResonanceIntegration(unittest.TestCase):
    def test_accessor_returns_summary_without_side_effects(self) -> None:
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        before_route = "reuse"
        item = {"type": "question", "text": "test", "graph_mode": before_route}
        _ = agent.process_item(item)
        summary = agent.get_strategy_calibration_summary()
        self.assertIn("overview", summary)
        self.assertEqual(item["graph_mode"], before_route)

    def test_missing_adoption_feedback_is_safe(self) -> None:
        stats = build_per_strategy_calibration_stats([{"strategy_id": "s1"}], [], [], {})
        self.assertEqual(len(stats), 1)


if __name__ == "__main__":
    unittest.main()
