# -*- coding: utf-8 -*-
"""Tests for alignment_strategy_aggregation module.

Covers:
- Pattern-level aggregation
- Strategy-level aggregation
- Global summary quality
- Safety (no mutation, no routing changes)
- Metrics
- ResonanceAgent integration
"""
from __future__ import annotations

import sys
import os
import unittest
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modules"))

from modules.agent.alignment_strategy_aggregation import (
    AlignmentStrategyAggregationMetrics,
    build_pattern_feedback_stats,
    build_strategy_feedback_aggregation_summary,
    build_strategy_feedback_stats,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _ev(
    strategy_id: str = "strat_a",
    pattern_ids: list[str] | None = None,
    label: str = "effective",
    response: float = 0.7,
    goal: float = 0.6,
    softening: bool = False,
) -> dict[str, Any]:
    return {
        "strategy_id": strategy_id,
        "pattern_ids": pattern_ids or ["pat_1"],
        "feedback_label": label,
        "was_effective": label == "effective",
        "response_score": response,
        "goal_alignment_score": goal,
        "softening_detected": softening,
    }


def _agent() -> Any:
    try:
        from agent.resonance_agent import ResonanceAgent
    except ImportError:
        from modules.agent.resonance_agent import ResonanceAgent
    return ResonanceAgent(anchor=[], llm_fn=None)


# ---------------------------------------------------------------------------
# Pattern aggregation
# ---------------------------------------------------------------------------

class TestPatternAggregation(unittest.TestCase):

    def test_empty_events_returns_empty_list(self) -> None:
        self.assertEqual(build_pattern_feedback_stats([]), [])

    def test_none_events_returns_empty_list(self) -> None:
        self.assertEqual(build_pattern_feedback_stats(None), [])  # type: ignore[arg-type]

    def test_single_event_single_pattern(self) -> None:
        result = build_pattern_feedback_stats([_ev(pattern_ids=["p1"])])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["pattern_id"], "p1")
        self.assertEqual(result[0]["times_recommended"], 1)

    def test_repeated_events_increment_counts(self) -> None:
        events = [
            _ev(pattern_ids=["p1"], label="effective"),
            _ev(pattern_ids=["p1"], label="effective"),
            _ev(pattern_ids=["p1"], label="neutral"),
        ]
        result = build_pattern_feedback_stats(events)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["times_recommended"], 3)

    def test_effective_total_correct(self) -> None:
        events = [
            _ev(pattern_ids=["p1"], label="effective"),
            _ev(pattern_ids=["p1"], label="ineffective"),
        ]
        self.assertEqual(build_pattern_feedback_stats(events)[0]["effective_total"], 1)

    def test_neutral_total_correct(self) -> None:
        events = [
            _ev(pattern_ids=["p1"], label="neutral"),
            _ev(pattern_ids=["p1"], label="effective"),
        ]
        self.assertEqual(build_pattern_feedback_stats(events)[0]["neutral_total"], 1)

    def test_ineffective_total_correct(self) -> None:
        events = [
            _ev(pattern_ids=["p1"], label="ineffective"),
            _ev(pattern_ids=["p1"], label="ineffective"),
        ]
        self.assertEqual(build_pattern_feedback_stats(events)[0]["ineffective_total"], 2)

    def test_effective_rate_correct(self) -> None:
        events = [
            _ev(pattern_ids=["p1"], label="effective"),
            _ev(pattern_ids=["p1"], label="neutral"),
            _ev(pattern_ids=["p1"], label="neutral"),
            _ev(pattern_ids=["p1"], label="neutral"),
        ]
        self.assertAlmostEqual(
            build_pattern_feedback_stats(events)[0]["effective_rate"], 0.25, places=3
        )

    def test_softening_positive_rate_correct(self) -> None:
        events = [
            _ev(pattern_ids=["p1"], softening=True),
            _ev(pattern_ids=["p1"], softening=True),
            _ev(pattern_ids=["p1"], softening=False),
            _ev(pattern_ids=["p1"], softening=False),
        ]
        self.assertAlmostEqual(
            build_pattern_feedback_stats(events)[0]["softening_positive_rate"], 0.5, places=3
        )

    def test_avg_response_score_correct(self) -> None:
        events = [
            _ev(pattern_ids=["p1"], response=0.8),
            _ev(pattern_ids=["p1"], response=0.4),
        ]
        self.assertAlmostEqual(
            build_pattern_feedback_stats(events)[0]["avg_response_score"], 0.6, places=3
        )

    def test_avg_goal_alignment_score_correct(self) -> None:
        events = [
            _ev(pattern_ids=["p1"], goal=1.0),
            _ev(pattern_ids=["p1"], goal=0.0),
        ]
        self.assertAlmostEqual(
            build_pattern_feedback_stats(events)[0]["avg_goal_alignment_score"], 0.5, places=3
        )

    def test_multi_pattern_ids_per_event_counted_independently(self) -> None:
        events = [_ev(pattern_ids=["p1", "p2"], label="effective")]
        result = build_pattern_feedback_stats(events)
        ids = {r["pattern_id"] for r in result}
        self.assertEqual(ids, {"p1", "p2"})

    def test_output_has_stable_keys(self) -> None:
        result = build_pattern_feedback_stats([_ev()])
        expected = {
            "pattern_id", "times_recommended", "effective_total",
            "neutral_total", "ineffective_total", "effective_rate",
            "softening_positive_rate", "avg_response_score",
            "avg_goal_alignment_score", "last_feedback_label",
            "linked_strategy_ids_top",
        }
        self.assertEqual(set(result[0].keys()), expected)


# ---------------------------------------------------------------------------
# Strategy aggregation
# ---------------------------------------------------------------------------

class TestStrategyAggregation(unittest.TestCase):

    def test_single_event_single_strategy(self) -> None:
        result = build_strategy_feedback_stats([_ev(strategy_id="s1")])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["strategy_id"], "s1")
        self.assertEqual(result[0]["times_presented"], 1)

    def test_repeated_events_increment_counts(self) -> None:
        events = [_ev(strategy_id="s1")] * 4
        result = build_strategy_feedback_stats(events)
        self.assertEqual(result[0]["times_presented"], 4)

    def test_linked_pattern_ids_collected(self) -> None:
        events = [
            _ev(strategy_id="s1", pattern_ids=["p1", "p2"]),
            _ev(strategy_id="s1", pattern_ids=["p1"]),
        ]
        result = build_strategy_feedback_stats(events)
        self.assertIn("p1", result[0]["linked_pattern_ids_top"])

    def test_last_feedback_label_updated(self) -> None:
        events = [
            _ev(strategy_id="s1", label="neutral"),
            _ev(strategy_id="s1", label="effective"),
        ]
        result = build_strategy_feedback_stats(events)
        self.assertEqual(result[0]["last_feedback_label"], "effective")

    def test_strategy_effective_rate_correct(self) -> None:
        events = [
            _ev(strategy_id="s1", label="effective"),
            _ev(strategy_id="s1", label="effective"),
            _ev(strategy_id="s1", label="neutral"),
            _ev(strategy_id="s1", label="neutral"),
        ]
        self.assertAlmostEqual(
            build_strategy_feedback_stats(events)[0]["effective_rate"], 0.5, places=3
        )

    def test_output_has_stable_keys(self) -> None:
        result = build_strategy_feedback_stats([_ev()])
        expected = {
            "strategy_id", "times_presented", "effective_total",
            "neutral_total", "ineffective_total", "effective_rate",
            "avg_response_score", "avg_goal_alignment_score",
            "linked_pattern_ids_top", "last_feedback_label",
        }
        self.assertEqual(set(result[0].keys()), expected)

    def test_empty_strategy_id_skipped(self) -> None:
        events = [_ev(strategy_id="")]
        self.assertEqual(build_strategy_feedback_stats(events), [])


# ---------------------------------------------------------------------------
# Summary quality
# ---------------------------------------------------------------------------

class TestSummaryQuality(unittest.TestCase):

    def _events(self, n_eff: int = 3, n_ineff: int = 1) -> list[dict]:
        events = []
        for i in range(n_eff):
            events.append(_ev(
                strategy_id=f"s_eff_{i}",
                pattern_ids=[f"p_eff_{i}"],
                label="effective",
                softening=True,
            ))
        for i in range(n_ineff):
            events.append(_ev(
                strategy_id=f"s_ineff_{i}",
                pattern_ids=[f"p_ineff_{i}"],
                label="ineffective",
                softening=False,
            ))
        return events

    def test_top_effective_patterns_capped(self) -> None:
        events = [_ev(pattern_ids=[f"p{i}"], label="effective") for i in range(10)]
        summary = build_strategy_feedback_aggregation_summary(events, top_n=3)
        self.assertLessEqual(len(summary["top_effective_patterns"]), 3)

    def test_top_ineffective_patterns_capped(self) -> None:
        events = [_ev(pattern_ids=[f"p{i}"], label="ineffective") for i in range(10)]
        summary = build_strategy_feedback_aggregation_summary(events, top_n=3)
        self.assertLessEqual(len(summary["top_ineffective_patterns"]), 3)

    def test_top_effective_strategies_capped(self) -> None:
        events = [_ev(strategy_id=f"s{i}", label="effective") for i in range(10)]
        summary = build_strategy_feedback_aggregation_summary(events, top_n=3)
        self.assertLessEqual(len(summary["top_effective_strategies"]), 3)

    def test_global_effective_rate_correct(self) -> None:
        events = self._events(n_eff=3, n_ineff=1)
        summary = build_strategy_feedback_aggregation_summary(events)
        self.assertAlmostEqual(summary["global_effective_rate"], 0.75, places=3)

    def test_global_softening_positive_rate_correct(self) -> None:
        events = self._events(n_eff=2, n_ineff=2)
        summary = build_strategy_feedback_aggregation_summary(events)
        # 2 softening=True (n_eff) out of 4 total
        self.assertAlmostEqual(summary["global_softening_positive_rate"], 0.5, places=3)

    def test_output_json_serialisable(self) -> None:
        import json
        summary = build_strategy_feedback_aggregation_summary(self._events())
        # Should not raise
        json.dumps(summary)

    def test_output_has_stable_keys(self) -> None:
        summary = build_strategy_feedback_aggregation_summary([])
        expected = {
            "total_patterns_seen", "total_strategies_seen",
            "top_effective_patterns", "top_ineffective_patterns",
            "top_effective_strategies", "top_ineffective_strategies",
            "global_effective_rate", "global_softening_positive_rate",
        }
        self.assertEqual(set(summary.keys()), expected)

    def test_empty_events_returns_zero_summary(self) -> None:
        summary = build_strategy_feedback_aggregation_summary([])
        self.assertEqual(summary["total_patterns_seen"], 0)
        self.assertEqual(summary["global_effective_rate"], 0.0)


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------

class TestSafety(unittest.TestCase):

    def test_aggregation_does_not_mutate_events(self) -> None:
        events = [_ev()]
        original = [dict(e) for e in events]
        build_pattern_feedback_stats(events)
        build_strategy_feedback_stats(events)
        self.assertEqual(events, original)

    def test_aggregation_does_not_change_route_key(self) -> None:
        agent = _agent()
        agent._record_strategy_outcome_feedback(
            [{"strategy_id": "s1", "based_on_pattern_ids": ["p1"]}],
            {"softening_detected": True, "response_score": 0.8},
        )
        agg = agent.get_alignment_strategy_aggregation()
        self.assertNotIn("_forced_route_key", agent.__dict__)
        self.assertIsInstance(agg, dict)

    def test_aggregation_does_not_change_graph_mode(self) -> None:
        agent = _agent()
        agent.get_alignment_strategy_aggregation()
        self.assertFalse(hasattr(agent, "_graph_mode_override"))

    def test_aggregation_does_not_break_reuse_mode(self) -> None:
        agent = _agent()
        agent._record_strategy_outcome_feedback(
            [{"strategy_id": "s1", "based_on_pattern_ids": ["p1"]}],
            {"graph_mode": "reuse", "response_score": 0.7},
        )
        agg = agent.get_alignment_strategy_aggregation()
        self.assertIn("pattern_stats", agg)

    def test_aggregation_does_not_write_to_prompt(self) -> None:
        events = [_ev()]
        for builder in [build_pattern_feedback_stats, build_strategy_feedback_stats]:
            result = builder(events)
            for item in result:
                for v in item.values():
                    if isinstance(v, str):
                        self.assertNotIn("SYSTEM:", v)
                        self.assertNotIn("<<SYS>>", v)

    def test_aggregation_does_not_change_feedback_or_recommender(self) -> None:
        agent = _agent()
        agent._record_strategy_outcome_feedback(
            [{"strategy_id": "s1", "based_on_pattern_ids": ["p1"]}],
            {"softening_detected": True},
        )
        feedback_before = list(agent.get_strategy_outcome_feedback_events())
        agent.get_alignment_strategy_aggregation()
        feedback_after = list(agent.get_strategy_outcome_feedback_events())
        self.assertEqual(feedback_before, feedback_after)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

class TestAggregationMetrics(unittest.TestCase):

    def test_calls_total_increments(self) -> None:
        agent = _agent()
        agent._record_strategy_outcome_feedback(
            [{"strategy_id": "s1", "based_on_pattern_ids": ["p1"]}],
            {"softening_detected": True},
        )
        agent.get_alignment_strategy_aggregation()
        m = agent.get_alignment_strategy_aggregation_metrics()
        self.assertEqual(m["calls_total"], 1)

    def test_events_processed_total(self) -> None:
        agent = _agent()
        agent._record_strategy_outcome_feedback(
            [{"strategy_id": "s1", "based_on_pattern_ids": ["p1"]},
             {"strategy_id": "s2", "based_on_pattern_ids": ["p2"]}],
            {"softening_detected": False, "response_score": 0.5},
        )
        agent.get_alignment_strategy_aggregation()
        m = agent.get_alignment_strategy_aggregation_metrics()
        self.assertEqual(m["events_processed_total"], 2)

    def test_unique_patterns_total(self) -> None:
        agent = _agent()
        agent._record_strategy_outcome_feedback(
            [{"strategy_id": "s1", "based_on_pattern_ids": ["p1", "p2"]}],
            {"softening_detected": True},
        )
        agent.get_alignment_strategy_aggregation()
        m = agent.get_alignment_strategy_aggregation_metrics()
        self.assertEqual(m["unique_patterns_total"], 2)

    def test_unique_strategies_total(self) -> None:
        agent = _agent()
        agent._record_strategy_outcome_feedback(
            [{"strategy_id": "s1", "based_on_pattern_ids": ["p1"]},
             {"strategy_id": "s2", "based_on_pattern_ids": ["p1"]}],
            {"softening_detected": True},
        )
        agent.get_alignment_strategy_aggregation()
        m = agent.get_alignment_strategy_aggregation_metrics()
        self.assertEqual(m["unique_strategies_total"], 2)

    def test_avg_events_per_pattern(self) -> None:
        m = AlignmentStrategyAggregationMetrics(
            events_processed_total=6,
            unique_patterns_total=3,
        )
        self.assertAlmostEqual(m.avg_events_per_pattern, 2.0, places=3)

    def test_avg_events_per_strategy(self) -> None:
        m = AlignmentStrategyAggregationMetrics(
            events_processed_total=10,
            unique_strategies_total=5,
        )
        self.assertAlmostEqual(m.avg_events_per_strategy, 2.0, places=3)

    def test_empty_total_increments(self) -> None:
        agent = _agent()
        # No feedback events recorded → aggregation will be empty
        agent.get_alignment_strategy_aggregation()
        m = agent.get_alignment_strategy_aggregation_metrics()
        self.assertEqual(m["empty_total"], 1)

    def test_nonempty_total_increments(self) -> None:
        agent = _agent()
        agent._record_strategy_outcome_feedback(
            [{"strategy_id": "s1", "based_on_pattern_ids": ["p1"]}],
            {"softening_detected": True},
        )
        agent.get_alignment_strategy_aggregation()
        m = agent.get_alignment_strategy_aggregation_metrics()
        self.assertEqual(m["nonempty_total"], 1)

    def test_metrics_to_dict_has_all_keys(self) -> None:
        m = AlignmentStrategyAggregationMetrics()
        d = m.to_dict()
        expected = {
            "calls_total", "events_processed_total",
            "unique_patterns_total", "unique_strategies_total",
            "empty_total", "nonempty_total",
            "avg_events_per_pattern", "avg_events_per_strategy",
        }
        self.assertEqual(set(d.keys()), expected)


# ---------------------------------------------------------------------------
# ResonanceAgent integration
# ---------------------------------------------------------------------------

class TestAgentIntegration(unittest.TestCase):

    def test_accessor_returns_aggregation_without_side_effects(self) -> None:
        agent = _agent()
        result = agent.get_alignment_strategy_aggregation()
        self.assertIn("pattern_stats", result)
        self.assertIn("strategy_stats", result)
        self.assertIn("summary", result)

    def test_no_feedback_events_handled_safely(self) -> None:
        agent = _agent()
        result = agent.get_alignment_strategy_aggregation()
        self.assertEqual(result["pattern_stats"], [])
        self.assertEqual(result["strategy_stats"], [])
        self.assertEqual(result["summary"]["total_patterns_seen"], 0)

    def test_existing_alignment_outputs_intact(self) -> None:
        agent = _agent()
        agent.get_alignment_strategy_aggregation()
        # Check upstream layers are still accessible
        self.assertIsInstance(agent.get_alignment_digest(), dict)
        self.assertIsInstance(agent.get_alignment_success_patterns(), list)
        self.assertIsInstance(agent.get_strategy_feedback_summary(), dict)

    def test_bounded_storage_still_works(self) -> None:
        agent = _agent()
        for i in range(5):
            agent._record_strategy_outcome_feedback(
                [{"strategy_id": f"s{i}", "based_on_pattern_ids": [f"p{i}"]}],
                {"softening_detected": True},
            )
        events = agent.get_strategy_outcome_feedback_events()
        self.assertEqual(len(events), 5)
        agg = agent.get_alignment_strategy_aggregation()
        self.assertEqual(agg["summary"]["total_strategies_seen"], 5)


if __name__ == "__main__":
    unittest.main()
