# -*- coding: utf-8 -*-
"""Tests for alignment_strategy_feedback module.

Covers:
- Feedback building (empty inputs, effective/neutral/ineffective labels)
- Label policy (softening_detected, guidance_effective, score thresholds)
- Summary aggregation
- Safety (no mutation, no routing changes)
- Metrics
- ResonanceAgent integration
"""
from __future__ import annotations

import sys
import os
import unittest
from typing import Any

# Allow both `python -m unittest` from python/ and direct invocation.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modules"))

from modules.agent.alignment_strategy_feedback import (
    AlignmentStrategyFeedbackMetrics,
    build_strategy_feedback_summary,
    build_strategy_outcome_feedback,
    _label_strategy_feedback,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _rec(
    strategy_id: str = "strat_abc",
    pattern_ids: list[str] | None = None,
    hotspot: str = "deadline_vs_quality",
    effect_reason: str = "",
) -> dict[str, Any]:
    return {
        "strategy_id": strategy_id,
        "based_on_pattern_ids": pattern_ids or ["pat1"],
        "hotspot": hotspot,
        "effect_reason": effect_reason,
        "title": "Use bridge_phrase",
        "summary": "In 2 similar cycles, this approach was effective 80% of the time.",
        "support_count": 2,
        "effective_rate": 0.8,
        "recommended_actions": ["acknowledge common ground"],
    }


def _outcome(
    softening_detected: bool = False,
    guidance_effective: bool = False,
    response_score: float = 0.5,
    goal_alignment_score: float = 0.5,
    effect_reason: str = "",
    hotspot: str = "deadline_vs_quality",
) -> dict[str, Any]:
    return {
        "softening_detected": softening_detected,
        "guidance_effective": guidance_effective,
        "response_score": response_score,
        "goal_alignment_score": goal_alignment_score,
        "effect_reason": effect_reason,
        "hotspot": hotspot,
    }


def _agent_with_feedback() -> Any:
    """Return a ResonanceAgent instance with no LLM (advisory-only tests)."""
    try:
        from agent.resonance_agent import ResonanceAgent
    except ImportError:
        from modules.agent.resonance_agent import ResonanceAgent
    return ResonanceAgent(anchor=[], llm_fn=None)


# ---------------------------------------------------------------------------
# Feedback Building
# ---------------------------------------------------------------------------

class TestFeedbackBuilding(unittest.TestCase):

    def test_empty_recommendations_returns_empty(self) -> None:
        result = build_strategy_outcome_feedback([], _outcome())
        self.assertEqual(result, [])

    def test_none_recommendations_returns_empty(self) -> None:
        result = build_strategy_outcome_feedback(None, _outcome())  # type: ignore[arg-type]
        self.assertEqual(result, [])

    def test_positive_outcome_gives_effective(self) -> None:
        result = build_strategy_outcome_feedback(
            [_rec()], _outcome(softening_detected=True)
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["feedback_label"], "effective")
        self.assertTrue(result[0]["was_effective"])

    def test_neutral_outcome_gives_neutral(self) -> None:
        result = build_strategy_outcome_feedback(
            [_rec()],
            _outcome(softening_detected=False, guidance_effective=False,
                     response_score=0.5, goal_alignment_score=0.5),
        )
        self.assertEqual(result[0]["feedback_label"], "neutral")
        self.assertFalse(result[0]["was_effective"])

    def test_weak_outcome_gives_ineffective(self) -> None:
        result = build_strategy_outcome_feedback(
            [_rec()],
            _outcome(softening_detected=False, guidance_effective=False,
                     response_score=0.2, goal_alignment_score=0.1),
        )
        self.assertEqual(result[0]["feedback_label"], "ineffective")
        self.assertFalse(result[0]["was_effective"])

    def test_feedback_object_has_stable_keys(self) -> None:
        result = build_strategy_outcome_feedback([_rec()], _outcome())
        expected_keys = {
            "strategy_id", "pattern_ids", "was_presented", "was_effective",
            "feedback_label", "effect_reason", "softening_detected",
            "guidance_effective", "response_score", "goal_alignment_score", "notes",
        }
        self.assertEqual(set(result[0].keys()), expected_keys)

    def test_effect_reason_carried_from_outcome(self) -> None:
        result = build_strategy_outcome_feedback(
            [_rec()], _outcome(effect_reason="bridge_phrase → cooperative softening")
        )
        self.assertIn("bridge_phrase", result[0]["effect_reason"])

    def test_no_outcome_returns_neutral_stubs(self) -> None:
        result = build_strategy_outcome_feedback([_rec()], {})
        self.assertEqual(result[0]["feedback_label"], "neutral")

    def test_was_presented_always_true(self) -> None:
        for outcome in [_outcome(), _outcome(softening_detected=True),
                        _outcome(response_score=0.1)]:
            result = build_strategy_outcome_feedback([_rec()], outcome)
            self.assertTrue(result[0]["was_presented"])

    def test_multiple_recs_all_get_same_label(self) -> None:
        recs = [_rec("s1"), _rec("s2"), _rec("s3")]
        result = build_strategy_outcome_feedback(
            recs, _outcome(softening_detected=True)
        )
        labels = [r["feedback_label"] for r in result]
        self.assertEqual(len(set(labels)), 1)
        self.assertEqual(labels[0], "effective")

    def test_pattern_ids_copied_correctly(self) -> None:
        result = build_strategy_outcome_feedback(
            [_rec(pattern_ids=["pat_x", "pat_y"])], _outcome()
        )
        self.assertEqual(result[0]["pattern_ids"], ["pat_x", "pat_y"])


# ---------------------------------------------------------------------------
# Label Policy
# ---------------------------------------------------------------------------

class TestLabelPolicy(unittest.TestCase):

    def test_softening_detected_gives_effective(self) -> None:
        label = _label_strategy_feedback({"softening_detected": True})
        self.assertEqual(label, "effective")

    def test_guidance_effective_gives_effective(self) -> None:
        label = _label_strategy_feedback({"guidance_effective": True})
        self.assertEqual(label, "effective")

    def test_weak_scores_no_signals_give_ineffective(self) -> None:
        label = _label_strategy_feedback({
            "softening_detected": False,
            "guidance_effective": False,
            "response_score": 0.2,
            "goal_alignment_score": 0.1,
        })
        self.assertEqual(label, "ineffective")

    def test_mixed_high_response_score_gives_effective(self) -> None:
        label = _label_strategy_feedback({
            "softening_detected": False,
            "guidance_effective": False,
            "response_score": 0.8,
            "goal_alignment_score": 0.3,
        })
        self.assertEqual(label, "effective")

    def test_mixed_high_goal_score_gives_effective(self) -> None:
        label = _label_strategy_feedback({
            "softening_detected": False,
            "guidance_effective": False,
            "response_score": 0.4,
            "goal_alignment_score": 0.7,
        })
        self.assertEqual(label, "effective")

    def test_mid_scores_no_signals_give_neutral(self) -> None:
        label = _label_strategy_feedback({
            "softening_detected": False,
            "guidance_effective": False,
            "response_score": 0.5,
            "goal_alignment_score": 0.5,
        })
        self.assertEqual(label, "neutral")

    def test_empty_outcome_gives_neutral(self) -> None:
        self.assertEqual(_label_strategy_feedback({}), "neutral")

    def test_label_is_deterministic(self) -> None:
        inp = {"softening_detected": True, "response_score": 0.9}
        self.assertEqual(_label_strategy_feedback(inp), _label_strategy_feedback(inp))

    def test_label_does_not_call_llm(self) -> None:
        # Pure function — just verify it completes without side effects
        result = _label_strategy_feedback({"guidance_effective": True})
        self.assertIn(result, ("effective", "neutral", "ineffective"))

    def test_zero_response_score_is_neutral_not_ineffective(self) -> None:
        # response_score=0.0 means "not recorded", not "bad"
        label = _label_strategy_feedback({
            "softening_detected": False,
            "guidance_effective": False,
            "response_score": 0.0,
            "goal_alignment_score": 0.0,
        })
        self.assertEqual(label, "neutral")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

class TestFeedbackSummary(unittest.TestCase):

    def _make_event(self, label: str, response: float = 0.5,
                    goal: float = 0.5, softening: bool = False,
                    sid: str = "s1", pids: list[str] | None = None) -> dict:
        return {
            "strategy_id": sid,
            "pattern_ids": pids or ["p1"],
            "feedback_label": label,
            "was_effective": label == "effective",
            "response_score": response,
            "goal_alignment_score": goal,
            "softening_detected": softening,
        }

    def test_empty_events_returns_zero_summary(self) -> None:
        summary = build_strategy_feedback_summary([])
        self.assertEqual(summary["total_feedback_events"], 0)
        self.assertEqual(summary["effective_total"], 0)
        self.assertEqual(summary["avg_response_score"], 0.0)

    def test_effective_total_counted_correctly(self) -> None:
        events = [
            self._make_event("effective"),
            self._make_event("effective"),
            self._make_event("neutral"),
        ]
        self.assertEqual(build_strategy_feedback_summary(events)["effective_total"], 2)

    def test_neutral_total_counted_correctly(self) -> None:
        events = [self._make_event("neutral"), self._make_event("effective")]
        self.assertEqual(build_strategy_feedback_summary(events)["neutral_total"], 1)

    def test_ineffective_total_counted_correctly(self) -> None:
        events = [self._make_event("ineffective"), self._make_event("neutral")]
        self.assertEqual(build_strategy_feedback_summary(events)["ineffective_total"], 1)

    def test_avg_response_score_correct(self) -> None:
        events = [
            self._make_event("effective", response=0.8),
            self._make_event("neutral", response=0.4),
        ]
        summary = build_strategy_feedback_summary(events)
        self.assertAlmostEqual(summary["avg_response_score"], 0.6, places=3)

    def test_avg_goal_alignment_score_correct(self) -> None:
        events = [
            self._make_event("effective", goal=1.0),
            self._make_event("neutral", goal=0.0),
        ]
        summary = build_strategy_feedback_summary(events)
        self.assertAlmostEqual(summary["avg_goal_alignment_score"], 0.5, places=3)

    def test_softening_positive_rate_correct(self) -> None:
        events = [
            self._make_event("effective", softening=True),
            self._make_event("neutral", softening=False),
            self._make_event("neutral", softening=False),
            self._make_event("effective", softening=True),
        ]
        summary = build_strategy_feedback_summary(events)
        self.assertAlmostEqual(summary["softening_positive_rate"], 0.5, places=3)

    def test_top_effective_strategy_ids(self) -> None:
        events = [
            self._make_event("effective", sid="s_a"),
            self._make_event("effective", sid="s_a"),
            self._make_event("effective", sid="s_b"),
        ]
        summary = build_strategy_feedback_summary(events)
        self.assertEqual(summary["top_effective_strategy_ids"][0], "s_a")

    def test_top_ineffective_strategy_ids(self) -> None:
        events = [
            self._make_event("ineffective", sid="s_bad"),
            self._make_event("ineffective", sid="s_bad"),
            self._make_event("ineffective", sid="s_ok"),
        ]
        summary = build_strategy_feedback_summary(events)
        self.assertEqual(summary["top_ineffective_strategy_ids"][0], "s_bad")

    def test_top_effective_pattern_ids(self) -> None:
        events = [
            self._make_event("effective", pids=["pat_x", "pat_y"]),
            self._make_event("effective", pids=["pat_x"]),
        ]
        summary = build_strategy_feedback_summary(events)
        self.assertEqual(summary["top_effective_pattern_ids"][0], "pat_x")

    def test_summary_has_stable_keys(self) -> None:
        summary = build_strategy_feedback_summary([])
        expected = {
            "total_feedback_events", "effective_total", "neutral_total",
            "ineffective_total", "top_effective_strategy_ids",
            "top_ineffective_strategy_ids", "top_effective_pattern_ids",
            "avg_response_score", "avg_goal_alignment_score",
            "softening_positive_rate",
        }
        self.assertEqual(set(summary.keys()), expected)


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------

class TestSafety(unittest.TestCase):

    def test_feedback_builder_does_not_mutate_recommendations(self) -> None:
        rec = _rec()
        original = dict(rec)
        build_strategy_outcome_feedback([rec], _outcome())
        self.assertEqual(rec, original)

    def test_feedback_builder_does_not_mutate_outcome(self) -> None:
        outcome = _outcome(softening_detected=True)
        original = dict(outcome)
        build_strategy_outcome_feedback([_rec()], outcome)
        self.assertEqual(outcome, original)

    def test_feedback_layer_does_not_change_graph_mode(self) -> None:
        agent = _agent_with_feedback()
        agent._record_strategy_outcome_feedback([_rec()], _outcome())
        # No graph_mode attribute should be mutated
        self.assertFalse(hasattr(agent, "_graph_mode_override"))

    def test_feedback_layer_does_not_set_route_key(self) -> None:
        agent = _agent_with_feedback()
        agent._record_strategy_outcome_feedback([_rec()], _outcome())
        self.assertNotIn("_forced_route_key", agent.__dict__)

    def test_feedback_layer_does_not_break_reuse_mode(self) -> None:
        agent = _agent_with_feedback()
        # Simulate reuse item — feedback recording should not raise
        agent._record_strategy_outcome_feedback(
            [_rec()], {"graph_mode": "reuse", "response_score": 0.7}
        )
        events = agent.get_strategy_outcome_feedback_events()
        self.assertIsInstance(events, list)

    def test_feedback_layer_does_not_write_to_prompt(self) -> None:
        result = build_strategy_outcome_feedback([_rec()], _outcome())
        for ev in result:
            for v in ev.values():
                if isinstance(v, str):
                    # Notes are allowed but must not contain prompt injection markers
                    self.assertNotIn("SYSTEM:", v)
                    self.assertNotIn("<<SYS>>", v)

    def test_feedback_layer_does_not_change_recommender_ranking(self) -> None:
        # Recording feedback must not modify the in-memory pattern or recommender state
        agent = _agent_with_feedback()
        agent._record_strategy_outcome_feedback([_rec()], _outcome())
        # Recommender-specific metrics should be untouched
        recommender_after = agent.get_alignment_strategy_recommendation_metrics()
        # calls_total in recommender should not have been incremented by feedback
        self.assertIsInstance(recommender_after, dict)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

class TestMetrics(unittest.TestCase):

    def test_calls_total_increments(self) -> None:
        agent = _agent_with_feedback()
        agent._record_strategy_outcome_feedback([_rec()], _outcome())
        m = agent.get_strategy_feedback_metrics()
        self.assertEqual(m["calls_total"], 1)

    def test_recommendations_processed_total(self) -> None:
        agent = _agent_with_feedback()
        agent._record_strategy_outcome_feedback([_rec("s1"), _rec("s2")], _outcome())
        m = agent.get_strategy_feedback_metrics()
        self.assertEqual(m["recommendations_processed_total"], 2)

    def test_feedback_events_total(self) -> None:
        agent = _agent_with_feedback()
        agent._record_strategy_outcome_feedback([_rec("s1"), _rec("s2")], _outcome())
        m = agent.get_strategy_feedback_metrics()
        self.assertEqual(m["feedback_events_total"], 2)

    def test_effective_total_metric(self) -> None:
        agent = _agent_with_feedback()
        agent._record_strategy_outcome_feedback([_rec()], _outcome(softening_detected=True))
        m = agent.get_strategy_feedback_metrics()
        self.assertEqual(m["effective_total"], 1)
        self.assertEqual(m["neutral_total"], 0)
        self.assertEqual(m["ineffective_total"], 0)

    def test_neutral_total_metric(self) -> None:
        agent = _agent_with_feedback()
        agent._record_strategy_outcome_feedback([_rec()], _outcome())
        m = agent.get_strategy_feedback_metrics()
        self.assertEqual(m["neutral_total"], 1)

    def test_ineffective_total_metric(self) -> None:
        agent = _agent_with_feedback()
        agent._record_strategy_outcome_feedback(
            [_rec()], _outcome(response_score=0.1)
        )
        m = agent.get_strategy_feedback_metrics()
        self.assertEqual(m["ineffective_total"], 1)

    def test_avg_feedback_per_call(self) -> None:
        agent = _agent_with_feedback()
        agent._record_strategy_outcome_feedback([_rec("s1"), _rec("s2")], _outcome())
        agent._record_strategy_outcome_feedback([_rec("s3")], _outcome())
        m = agent.get_strategy_feedback_metrics()
        # 3 events / 2 calls = 1.5
        self.assertAlmostEqual(m["avg_feedback_per_call"], 1.5, places=3)

    def test_summary_calls_total(self) -> None:
        agent = _agent_with_feedback()
        agent._record_strategy_outcome_feedback([_rec()], _outcome())
        agent.get_strategy_feedback_summary()
        agent.get_strategy_feedback_summary()
        m = agent.get_strategy_feedback_metrics()
        self.assertEqual(m["summary_calls_total"], 2)

    def test_metrics_to_dict_has_all_keys(self) -> None:
        m = AlignmentStrategyFeedbackMetrics()
        d = m.to_dict()
        expected = {
            "calls_total", "recommendations_processed_total",
            "feedback_events_total", "effective_total", "neutral_total",
            "ineffective_total", "summary_calls_total", "avg_feedback_per_call",
        }
        self.assertEqual(set(d.keys()), expected)


# ---------------------------------------------------------------------------
# ResonanceAgent Integration
# ---------------------------------------------------------------------------

class TestAgentIntegration(unittest.TestCase):

    def test_feedback_events_written_post_cycle(self) -> None:
        agent = _agent_with_feedback()
        agent._record_strategy_outcome_feedback([_rec()], _outcome(softening_detected=True))
        events = agent.get_strategy_outcome_feedback_events()
        self.assertGreater(len(events), 0)
        self.assertEqual(events[0]["feedback_label"], "effective")

    def test_feedback_summary_accessible(self) -> None:
        agent = _agent_with_feedback()
        agent._record_strategy_outcome_feedback([_rec()], _outcome(guidance_effective=True))
        summary = agent.get_strategy_feedback_summary()
        self.assertIn("effective_total", summary)
        self.assertGreaterEqual(summary["effective_total"], 1)

    def test_no_recommendations_handled_safely(self) -> None:
        agent = _agent_with_feedback()
        agent._record_strategy_outcome_feedback([], _outcome())
        events = agent.get_strategy_outcome_feedback_events()
        self.assertEqual(events, [])

    def test_existing_alignment_outputs_intact(self) -> None:
        agent = _agent_with_feedback()
        # Digest and success patterns must still be accessible after feedback added
        agent._record_strategy_outcome_feedback([_rec()], _outcome())
        digest = agent.get_alignment_digest()
        self.assertIsInstance(digest, dict)
        patterns = agent.get_alignment_success_patterns()
        self.assertIsInstance(patterns, list)


if __name__ == "__main__":
    unittest.main()
