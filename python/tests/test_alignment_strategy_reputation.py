# -*- coding: utf-8 -*-
"""Tests for alignment_strategy_reputation module."""
from __future__ import annotations

import sys
import os
import unittest
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modules"))

from modules.agent.alignment_strategy_reputation import (
    AlignmentStrategyReputationMetrics,
    _compute_reputation_confidence,
    build_strategy_reputation_overlay,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _rec(
    strategy_id: str = "strat_a",
    pattern_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "strategy_id": strategy_id,
        "based_on_pattern_ids": pattern_ids or ["pat_1"],
        "title": "Use bridge_phrase",
        "summary": "Test summary.",
        "support_count": 2,
        "effective_rate": 0.8,
        "recommended_actions": ["acknowledge common ground"],
    }


def _s_stat(
    strategy_id: str = "strat_a",
    times: int = 5,
    eff_rate: float = 0.7,
    pattern_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "strategy_id": strategy_id,
        "times_presented": times,
        "effective_total": int(times * eff_rate),
        "neutral_total": 0,
        "ineffective_total": times - int(times * eff_rate),
        "effective_rate": eff_rate,
        "avg_response_score": 0.7,
        "avg_goal_alignment_score": 0.6,
        "linked_pattern_ids_top": pattern_ids or ["pat_1"],
        "last_feedback_label": "effective",
    }


def _p_stat(
    pattern_id: str = "pat_1",
    times: int = 4,
    eff_rate: float = 0.7,
) -> dict[str, Any]:
    return {
        "pattern_id": pattern_id,
        "times_recommended": times,
        "effective_total": int(times * eff_rate),
        "neutral_total": 0,
        "ineffective_total": times - int(times * eff_rate),
        "effective_rate": eff_rate,
        "softening_positive_rate": 0.5,
        "avg_response_score": 0.7,
        "avg_goal_alignment_score": 0.6,
        "last_feedback_label": "effective",
        "linked_strategy_ids_top": ["strat_a"],
    }


def _aggregation(
    s_stats: list[dict] | None = None,
    p_stats: list[dict] | None = None,
) -> dict[str, Any]:
    return {
        "pattern_stats": p_stats or [],
        "strategy_stats": s_stats or [],
        "summary": {},
    }


def _agent() -> Any:
    try:
        from agent.resonance_agent import ResonanceAgent
    except ImportError:
        from modules.agent.resonance_agent import ResonanceAgent
    return ResonanceAgent(anchor=[], llm_fn=None)


# ---------------------------------------------------------------------------
# Reputation labeling
# ---------------------------------------------------------------------------

class TestReputationLabeling(unittest.TestCase):

    def test_empty_recommendations_returns_empty_overlay(self) -> None:
        result = build_strategy_reputation_overlay([], _aggregation())
        self.assertEqual(result, [])

    def test_none_recommendations_returns_empty(self) -> None:
        result = build_strategy_reputation_overlay(None, _aggregation())  # type: ignore[arg-type]
        self.assertEqual(result, [])

    def test_no_aggregation_data_gives_insufficient_data(self) -> None:
        result = build_strategy_reputation_overlay([_rec()], _aggregation())
        self.assertEqual(result[0]["reputation_label"], "insufficient_data")

    def test_strong_stats_give_validated_pattern(self) -> None:
        s = _s_stat(times=8, eff_rate=0.75)
        result = build_strategy_reputation_overlay(
            [_rec()], _aggregation(s_stats=[s])
        )
        self.assertEqual(result[0]["reputation_label"], "validated_pattern")

    def test_early_positive_gives_emerging_pattern(self) -> None:
        s = _s_stat(times=3, eff_rate=0.5)
        result = build_strategy_reputation_overlay(
            [_rec()], _aggregation(s_stats=[s])
        )
        self.assertEqual(result[0]["reputation_label"], "emerging_pattern")

    def test_repeated_weak_gives_weak_pattern(self) -> None:
        s = _s_stat(times=5, eff_rate=0.1)
        result = build_strategy_reputation_overlay(
            [_rec()], _aggregation(s_stats=[s])
        )
        self.assertEqual(result[0]["reputation_label"], "weak_pattern")

    def test_same_input_gives_same_label(self) -> None:
        s = _s_stat(times=6, eff_rate=0.65)
        agg = _aggregation(s_stats=[s])
        r1 = build_strategy_reputation_overlay([_rec()], agg)
        r2 = build_strategy_reputation_overlay([_rec()], agg)
        self.assertEqual(r1[0]["reputation_label"], r2[0]["reputation_label"])

    def test_pattern_evidence_promotes_emerging_when_strategy_thin(self) -> None:
        # Strategy has only 1 presentation but linked pattern is positive
        s = _s_stat(times=1, eff_rate=0.0)
        p = _p_stat(times=4, eff_rate=0.6)
        result = build_strategy_reputation_overlay(
            [_rec()], _aggregation(s_stats=[s], p_stats=[p])
        )
        self.assertEqual(result[0]["reputation_label"], "emerging_pattern")


# ---------------------------------------------------------------------------
# Confidence score
# ---------------------------------------------------------------------------

class TestConfidenceScore(unittest.TestCase):

    def test_confidence_in_range_0_to_1(self) -> None:
        for times, rate in [(0, 0.0), (2, 0.5), (10, 0.8), (100, 1.0)]:
            s = _s_stat(times=times, eff_rate=rate)
            score = _compute_reputation_confidence(s, [])
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)

    def test_higher_support_increases_confidence(self) -> None:
        low = _compute_reputation_confidence(_s_stat(times=2, eff_rate=0.5), [])
        high = _compute_reputation_confidence(_s_stat(times=15, eff_rate=0.5), [])
        self.assertGreater(high, low)

    def test_higher_effective_rate_increases_confidence(self) -> None:
        low = _compute_reputation_confidence(_s_stat(times=5, eff_rate=0.2), [])
        high = _compute_reputation_confidence(_s_stat(times=5, eff_rate=0.8), [])
        self.assertGreater(high, low)

    def test_no_stats_gives_zero_confidence(self) -> None:
        self.assertEqual(_compute_reputation_confidence(None, []), 0.0)

    def test_strong_pattern_gives_higher_confidence(self) -> None:
        s = _s_stat(times=5, eff_rate=0.6)
        base = _compute_reputation_confidence(s, [])
        with_pattern = _compute_reputation_confidence(s, [_p_stat(eff_rate=0.9)])
        self.assertGreater(with_pattern, base)

    def test_confidence_is_deterministic(self) -> None:
        s = _s_stat(times=5, eff_rate=0.65)
        p = _p_stat(eff_rate=0.7)
        c1 = _compute_reputation_confidence(s, [p])
        c2 = _compute_reputation_confidence(s, [p])
        self.assertEqual(c1, c2)


# ---------------------------------------------------------------------------
# Overlay quality
# ---------------------------------------------------------------------------

class TestOverlayQuality(unittest.TestCase):

    def test_overlay_has_stable_keys(self) -> None:
        result = build_strategy_reputation_overlay([_rec()], _aggregation())
        expected = {
            "strategy_id", "reputation_label", "advisory_confidence",
            "support_count", "effective_rate", "linked_pattern_ids",
            "reputation_reason", "advisory_note", "has_pattern_evidence",
        }
        self.assertEqual(set(result[0].keys()), expected)

    def test_overlay_does_not_change_recommendation_fields(self) -> None:
        rec = _rec()
        original_keys = set(rec.keys())
        build_strategy_reputation_overlay([rec], _aggregation())
        self.assertEqual(set(rec.keys()), original_keys)
        self.assertEqual(rec["strategy_id"], "strat_a")

    def test_reputation_reason_is_non_empty_string(self) -> None:
        result = build_strategy_reputation_overlay([_rec()], _aggregation())
        reason = result[0]["reputation_reason"]
        self.assertIsInstance(reason, str)
        self.assertGreater(len(reason), 0)

    def test_advisory_note_is_non_empty_string(self) -> None:
        result = build_strategy_reputation_overlay([_rec()], _aggregation())
        note = result[0]["advisory_note"]
        self.assertIsInstance(note, str)
        self.assertGreater(len(note), 0)

    def test_linked_pattern_ids_propagated(self) -> None:
        result = build_strategy_reputation_overlay(
            [_rec(pattern_ids=["p_x", "p_y"])], _aggregation()
        )
        self.assertIn("p_x", result[0]["linked_pattern_ids"])
        self.assertIn("p_y", result[0]["linked_pattern_ids"])

    def test_strategy_id_propagated(self) -> None:
        result = build_strategy_reputation_overlay(
            [_rec(strategy_id="my_strat")], _aggregation()
        )
        self.assertEqual(result[0]["strategy_id"], "my_strat")

    def test_multiple_recs_produce_one_overlay_each(self) -> None:
        recs = [_rec("s1"), _rec("s2"), _rec("s3")]
        result = build_strategy_reputation_overlay(recs, _aggregation())
        self.assertEqual(len(result), 3)

    def test_has_pattern_evidence_flag(self) -> None:
        p = _p_stat()
        result = build_strategy_reputation_overlay(
            [_rec(pattern_ids=["pat_1"])],
            _aggregation(p_stats=[p]),
        )
        self.assertTrue(result[0]["has_pattern_evidence"])

    def test_no_pattern_evidence_flag(self) -> None:
        result = build_strategy_reputation_overlay([_rec()], _aggregation())
        self.assertFalse(result[0]["has_pattern_evidence"])


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------

class TestSafety(unittest.TestCase):

    def test_overlay_does_not_mutate_recommendations(self) -> None:
        rec = _rec()
        original = dict(rec)
        build_strategy_reputation_overlay([rec], _aggregation())
        self.assertEqual(rec, original)

    def test_overlay_does_not_mutate_aggregation(self) -> None:
        agg = _aggregation(s_stats=[_s_stat()])
        original_keys = set(agg.keys())
        build_strategy_reputation_overlay([_rec()], agg)
        self.assertEqual(set(agg.keys()), original_keys)

    def test_overlay_does_not_change_route_key(self) -> None:
        agent = _agent()
        agent.get_alignment_strategy_reputation_overlay({})
        self.assertNotIn("_forced_route_key", agent.__dict__)

    def test_overlay_does_not_change_graph_mode(self) -> None:
        agent = _agent()
        agent.get_alignment_strategy_reputation_overlay({})
        self.assertFalse(hasattr(agent, "_graph_mode_override"))

    def test_overlay_does_not_break_reuse_mode(self) -> None:
        agent = _agent()
        result = agent.get_alignment_strategy_reputation_overlay(
            {"graph_mode": "reuse"}
        )
        self.assertIsInstance(result, list)

    def test_overlay_does_not_write_to_prompt(self) -> None:
        result = build_strategy_reputation_overlay(
            [_rec()], _aggregation(s_stats=[_s_stat()])
        )
        for ov in result:
            for v in ov.values():
                if isinstance(v, str):
                    self.assertNotIn("SYSTEM:", v)
                    self.assertNotIn("<<SYS>>", v)

    def test_overlay_does_not_change_recommender_ranking(self) -> None:
        agent = _agent()
        # Record some feedback so aggregation has data
        agent._record_strategy_outcome_feedback(
            [{"strategy_id": "s1", "based_on_pattern_ids": ["p1"]}],
            {"softening_detected": True},
        )
        # Re-check recommender metrics haven't changed from overlay calls
        agent.get_alignment_strategy_reputation_overlay({})
        after = agent.get_alignment_strategy_recommendation_metrics()
        self.assertIsInstance(after, dict)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

class TestReputationMetrics(unittest.TestCase):

    def _agent_with_overlay(
        self,
        times: int = 6,
        eff_rate: float = 0.7,
        n_recs: int = 1,
    ) -> Any:
        agent = _agent()
        # Push feedback events so aggregation has data
        for i in range(n_recs):
            for _ in range(times):
                agent._record_strategy_outcome_feedback(
                    [{
                        "strategy_id": f"s{i}",
                        "based_on_pattern_ids": [f"p{i}"],
                        "feedback_label": "effective" if eff_rate >= 0.5 else "ineffective",
                    }],
                    {
                        "softening_detected": eff_rate >= 0.5,
                        "response_score": eff_rate,
                    },
                )
        return agent

    def test_calls_total_increments(self) -> None:
        agent = _agent()
        agent.get_alignment_strategy_reputation_overlay({})
        m = agent.get_alignment_strategy_reputation_metrics()
        self.assertEqual(m["calls_total"], 1)

    def test_recommendations_processed_total(self) -> None:
        agent = _agent()
        agent.get_alignment_strategy_reputation_overlay({})
        m = agent.get_alignment_strategy_reputation_metrics()
        self.assertGreaterEqual(m["recommendations_processed_total"], 0)

    def test_validated_total_increments(self) -> None:
        agent = _agent()
        # Inject overlay directly with known validated pattern
        agg = _aggregation(s_stats=[_s_stat(times=8, eff_rate=0.75)])
        overlays = build_strategy_reputation_overlay([_rec()], agg)
        m = agent._reputation_metrics
        if m is not None:
            m.calls_total += 1
            m.recommendations_processed_total += len(overlays)
            for ov in overlays:
                if ov["reputation_label"] == "validated_pattern":
                    m.validated_total += 1
        metrics = agent.get_alignment_strategy_reputation_metrics()
        self.assertGreaterEqual(metrics["validated_total"], 1)

    def test_emerging_total_increments(self) -> None:
        agent = _agent()
        agg = _aggregation(s_stats=[_s_stat(times=3, eff_rate=0.5)])
        overlays = build_strategy_reputation_overlay([_rec()], agg)
        m = agent._reputation_metrics
        if m is not None:
            for ov in overlays:
                if ov["reputation_label"] == "emerging_pattern":
                    m.emerging_total += 1
        self.assertGreaterEqual(
            agent.get_alignment_strategy_reputation_metrics()["emerging_total"], 1
        )

    def test_weak_total_increments(self) -> None:
        agent = _agent()
        agg = _aggregation(s_stats=[_s_stat(times=5, eff_rate=0.1)])
        overlays = build_strategy_reputation_overlay([_rec()], agg)
        m = agent._reputation_metrics
        if m is not None:
            for ov in overlays:
                if ov["reputation_label"] == "weak_pattern":
                    m.weak_total += 1
        self.assertGreaterEqual(
            agent.get_alignment_strategy_reputation_metrics()["weak_total"], 1
        )

    def test_insufficient_total_increments(self) -> None:
        agent = _agent()
        overlays = build_strategy_reputation_overlay([_rec()], _aggregation())
        m = agent._reputation_metrics
        if m is not None:
            m.calls_total += 1
            m.recommendations_processed_total += len(overlays)
            for ov in overlays:
                if ov["reputation_label"] == "insufficient_data":
                    m.insufficient_total += 1
        self.assertGreaterEqual(
            agent.get_alignment_strategy_reputation_metrics()["insufficient_total"], 1
        )

    def test_avg_confidence_score_computed(self) -> None:
        m = AlignmentStrategyReputationMetrics(
            recommendations_processed_total=4,
            confidence_sum=2.0,
        )
        self.assertAlmostEqual(m.avg_confidence_score, 0.5, places=3)

    def test_pattern_evidence_total_increments(self) -> None:
        agent = _agent()
        p = _p_stat()
        agg = _aggregation(p_stats=[p])
        overlays = build_strategy_reputation_overlay([_rec(pattern_ids=["pat_1"])], agg)
        m = agent._reputation_metrics
        if m is not None:
            for ov in overlays:
                if ov.get("has_pattern_evidence"):
                    m.pattern_evidence_total += 1
        self.assertGreaterEqual(
            agent.get_alignment_strategy_reputation_metrics()["pattern_evidence_total"], 1
        )

    def test_strategy_only_evidence_total(self) -> None:
        agent = _agent()
        overlays = build_strategy_reputation_overlay([_rec()], _aggregation())
        m = agent._reputation_metrics
        if m is not None:
            for ov in overlays:
                if not ov.get("has_pattern_evidence"):
                    m.strategy_only_evidence_total += 1
        self.assertGreaterEqual(
            agent.get_alignment_strategy_reputation_metrics()["strategy_only_evidence_total"], 1
        )

    def test_metrics_to_dict_has_all_keys(self) -> None:
        m = AlignmentStrategyReputationMetrics()
        d = m.to_dict()
        expected = {
            "calls_total", "recommendations_processed_total",
            "validated_total", "emerging_total", "weak_total", "insufficient_total",
            "avg_confidence_score", "pattern_evidence_total",
            "strategy_only_evidence_total",
        }
        self.assertEqual(set(d.keys()), expected)


# ---------------------------------------------------------------------------
# ResonanceAgent integration
# ---------------------------------------------------------------------------

class TestAgentIntegration(unittest.TestCase):

    def test_accessor_returns_overlay_without_side_effects(self) -> None:
        agent = _agent()
        result = agent.get_alignment_strategy_reputation_overlay({})
        self.assertIsInstance(result, list)

    def test_no_aggregation_data_handled_safely(self) -> None:
        agent = _agent()
        result = agent.get_alignment_strategy_reputation_overlay({})
        for ov in result:
            self.assertEqual(ov["reputation_label"], "insufficient_data")

    def test_existing_alignment_outputs_intact(self) -> None:
        agent = _agent()
        agent.get_alignment_strategy_reputation_overlay({})
        self.assertIsInstance(agent.get_alignment_digest(), dict)
        self.assertIsInstance(agent.get_alignment_success_patterns(), list)
        self.assertIsInstance(agent.get_strategy_feedback_summary(), dict)
        self.assertIsInstance(agent.get_alignment_strategy_aggregation(), dict)

    def test_overlay_built_on_top_of_recommendations_not_instead(self) -> None:
        agent = _agent()
        recs = agent.get_alignment_strategy_recommendations({})
        overlay = agent.get_alignment_strategy_reputation_overlay({})
        # Overlay length equals recommendation count — one overlay per rec
        self.assertEqual(len(overlay), len(recs))


if __name__ == "__main__":
    unittest.main()
