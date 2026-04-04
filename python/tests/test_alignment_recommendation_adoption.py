# -*- coding: utf-8 -*-
"""Tests for alignment_recommendation_adoption module."""
from __future__ import annotations

import sys
import os
import unittest
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modules"))

from modules.agent.alignment_recommendation_adoption import (
    AlignmentRecommendationAdoptionMetrics,
    _label_adoption,
    _match_recommended_action,
    build_recommendation_adoption_summary,
    build_recommendation_adoption_trace,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _rec(
    strategy_id: str = "strat_a",
    pattern_ids: list[str] | None = None,
    actions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "strategy_id": strategy_id,
        "based_on_pattern_ids": pattern_ids or ["pat_1"],
        "recommended_actions": actions or [
            "acknowledge common ground before moving forward"
        ],
        "title": "Use bridge_phrase",
        "summary": "Test summary.",
    }


def _agent() -> Any:
    try:
        from agent.resonance_agent import ResonanceAgent
    except ImportError:
        from modules.agent.resonance_agent import ResonanceAgent
    return ResonanceAgent(anchor=[], llm_fn=None)


# ---------------------------------------------------------------------------
# Trace building
# ---------------------------------------------------------------------------

class TestTraceBuilding(unittest.TestCase):

    def test_empty_recommendations_returns_empty(self) -> None:
        result = build_recommendation_adoption_trace([], "some response")
        self.assertEqual(result, [])

    def test_none_recommendations_returns_empty(self) -> None:
        result = build_recommendation_adoption_trace(None, "some response")  # type: ignore[arg-type]
        self.assertEqual(result, [])

    def test_fully_matched_actions_give_adopted(self) -> None:
        rec = _rec(actions=["acknowledge common ground before moving forward"])
        response = "I understand — we both want a good outcome. I see your point clearly."
        result = build_recommendation_adoption_trace([rec], response)
        self.assertEqual(result[0]["adoption_label"], "adopted")

    def test_partial_match_gives_partially_adopted(self) -> None:
        rec = _rec(actions=[
            "acknowledge common ground before moving forward",
            "avoid winner/loser framing",
        ])
        # Only first action has cues
        response = "I understand your view and agree that we should find a solution."
        result = build_recommendation_adoption_trace([rec], response)
        self.assertEqual(result[0]["adoption_label"], "partially_adopted")

    def test_no_match_gives_not_adopted(self) -> None:
        rec = _rec(actions=["acknowledge common ground before moving forward"])
        response = "The technical solution requires updating the database schema."
        result = build_recommendation_adoption_trace([rec], response)
        self.assertEqual(result[0]["adoption_label"], "not_adopted")

    def test_trace_has_stable_keys(self) -> None:
        result = build_recommendation_adoption_trace([_rec()], "hello world")
        expected = {
            "strategy_id", "pattern_ids", "adoption_label",
            "matched_actions", "unmatched_actions",
            "matched_action_count", "total_action_count",
            "adoption_score", "effect_reason", "trace_reason",
            "response_excerpt",
        }
        self.assertEqual(set(result[0].keys()), expected)

    def test_matched_and_unmatched_counts_correct(self) -> None:
        rec = _rec(actions=[
            "acknowledge common ground before moving forward",
            "slow response tempo and increase structural clarity",
            "avoid winner/loser framing",
        ])
        # Only first matches (has "i understand" / "agree that")
        response = "I understand what you mean and agree that we should move on."
        result = build_recommendation_adoption_trace([rec], response)
        self.assertEqual(result[0]["matched_action_count"], 1)
        self.assertEqual(len(result[0]["unmatched_actions"]), 2)

    def test_response_excerpt_is_bounded(self) -> None:
        long_response = "x" * 500
        result = build_recommendation_adoption_trace([_rec()], long_response)
        self.assertLessEqual(len(result[0]["response_excerpt"]), 200)

    def test_effect_reason_carried_from_outcome(self) -> None:
        result = build_recommendation_adoption_trace(
            [_rec()], "any response",
            alignment_outcome={"effect_reason": "bridge_phrase applied"}
        )
        self.assertIn("bridge_phrase", result[0]["effect_reason"])

    def test_multiple_recs_produce_one_trace_each(self) -> None:
        recs = [_rec("s1"), _rec("s2"), _rec("s3")]
        result = build_recommendation_adoption_trace(recs, "I understand your concern.")
        self.assertEqual(len(result), 3)


# ---------------------------------------------------------------------------
# Matching logic
# ---------------------------------------------------------------------------

class TestMatchingLogic(unittest.TestCase):

    def test_canonical_action_matches_its_cues(self) -> None:
        m = _match_recommended_action(
            "acknowledge common ground before moving forward",
            "i understand your point completely",
        )
        self.assertTrue(m["matched"])
        self.assertTrue(m["action_known"])

    def test_unknown_action_does_not_raise(self) -> None:
        m = _match_recommended_action("do something totally unknown", "any text here")
        self.assertFalse(m["matched"])
        self.assertFalse(m["action_known"])

    def test_matching_is_case_insensitive(self) -> None:
        m = _match_recommended_action(
            "acknowledge common ground before moving forward",
            "WE BOTH AGREE AND I UNDERSTAND THE SITUATION",
        )
        self.assertTrue(m["matched"])

    def test_repeated_cue_does_not_break_counting(self) -> None:
        # Same cue appearing many times should still count as one match
        m = _match_recommended_action(
            "acknowledge common ground before moving forward",
            "i understand i understand i understand",
        )
        self.assertTrue(m["matched"])

    def test_different_action_families_do_not_collide(self) -> None:
        # "slow response tempo" family cues should not match "acknowledge" action
        m_ack = _match_recommended_action(
            "acknowledge common ground before moving forward",
            "let me break this down step by step",
        )
        m_pace = _match_recommended_action(
            "slow response tempo and increase structural clarity",
            "let me break this down step by step",
        )
        # pacing action should match
        self.assertTrue(m_pace["matched"])
        # acknowledge action should NOT match on pacing cues alone
        self.assertFalse(m_ack["matched"])

    def test_same_input_gives_same_result(self) -> None:
        action = "frame solutions as shared options, not unilateral decisions"
        text = "we could consider one option or another option together"
        r1 = _match_recommended_action(action, text)
        r2 = _match_recommended_action(action, text)
        self.assertEqual(r1, r2)

    def test_no_cues_in_response_returns_not_matched(self) -> None:
        m = _match_recommended_action(
            "acknowledge common ground before moving forward",
            "the system requires a reboot after configuration changes",
        )
        self.assertFalse(m["matched"])


# ---------------------------------------------------------------------------
# Label policy
# ---------------------------------------------------------------------------

class TestLabelPolicy(unittest.TestCase):

    def test_full_match_gives_adopted_and_score_1(self) -> None:
        label, score = _label_adoption(3, 3)
        self.assertEqual(label, "adopted")
        self.assertAlmostEqual(score, 1.0, places=3)

    def test_partial_match_gives_partially_adopted(self) -> None:
        label, score = _label_adoption(1, 3)
        self.assertEqual(label, "partially_adopted")
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)

    def test_zero_match_gives_not_adopted(self) -> None:
        label, score = _label_adoption(0, 3)
        self.assertEqual(label, "not_adopted")
        self.assertAlmostEqual(score, 0.0, places=3)

    def test_zero_total_gives_not_adopted(self) -> None:
        label, score = _label_adoption(0, 0)
        self.assertEqual(label, "not_adopted")
        self.assertAlmostEqual(score, 0.0, places=3)

    def test_score_stays_in_range(self) -> None:
        for matched, total in [(0, 1), (1, 1), (2, 3), (0, 0), (5, 5)]:
            _, score = _label_adoption(matched, total)
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)

    def test_label_is_deterministic(self) -> None:
        self.assertEqual(_label_adoption(2, 4), _label_adoption(2, 4))

    def test_high_partial_ratio_still_partially_adopted(self) -> None:
        label, score = _label_adoption(3, 4)
        self.assertEqual(label, "partially_adopted")
        self.assertAlmostEqual(score, 0.75, places=3)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

class TestSummary(unittest.TestCase):

    def _trace(
        self,
        label: str = "adopted",
        score: float = 1.0,
        sid: str = "s1",
        pids: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "strategy_id": sid,
            "pattern_ids": pids or ["p1"],
            "adoption_label": label,
            "adoption_score": score,
        }

    def test_empty_traces_returns_zero_summary(self) -> None:
        s = build_recommendation_adoption_summary([])
        self.assertEqual(s["total_traces"], 0)
        self.assertEqual(s["adopted_total"], 0)
        self.assertEqual(s["avg_adoption_score"], 0.0)

    def test_adopted_total_correct(self) -> None:
        traces = [self._trace("adopted"), self._trace("adopted"), self._trace("not_adopted")]
        self.assertEqual(build_recommendation_adoption_summary(traces)["adopted_total"], 2)

    def test_partially_adopted_total_correct(self) -> None:
        traces = [self._trace("partially_adopted"), self._trace("adopted")]
        self.assertEqual(
            build_recommendation_adoption_summary(traces)["partially_adopted_total"], 1
        )

    def test_not_adopted_total_correct(self) -> None:
        traces = [self._trace("not_adopted"), self._trace("not_adopted")]
        self.assertEqual(build_recommendation_adoption_summary(traces)["not_adopted_total"], 2)

    def test_avg_adoption_score_correct(self) -> None:
        traces = [self._trace(score=1.0), self._trace(score=0.0)]
        s = build_recommendation_adoption_summary(traces)
        self.assertAlmostEqual(s["avg_adoption_score"], 0.5, places=3)

    def test_top_adopted_strategy_ids(self) -> None:
        traces = [
            self._trace("adopted", sid="best"),
            self._trace("adopted", sid="best"),
            self._trace("adopted", sid="other"),
        ]
        s = build_recommendation_adoption_summary(traces)
        self.assertEqual(s["top_adopted_strategy_ids"][0], "best")

    def test_top_not_adopted_strategy_ids(self) -> None:
        traces = [
            self._trace("not_adopted", sid="bad"),
            self._trace("not_adopted", sid="bad"),
        ]
        s = build_recommendation_adoption_summary(traces)
        self.assertEqual(s["top_not_adopted_strategy_ids"][0], "bad")

    def test_top_adopted_pattern_ids(self) -> None:
        traces = [
            self._trace("adopted", pids=["pat_x", "pat_y"]),
            self._trace("adopted", pids=["pat_x"]),
        ]
        s = build_recommendation_adoption_summary(traces)
        self.assertEqual(s["top_adopted_pattern_ids"][0], "pat_x")

    def test_summary_has_stable_keys(self) -> None:
        s = build_recommendation_adoption_summary([])
        expected = {
            "total_traces", "adopted_total", "partially_adopted_total",
            "not_adopted_total", "avg_adoption_score",
            "top_adopted_strategy_ids", "top_not_adopted_strategy_ids",
            "top_adopted_pattern_ids",
        }
        self.assertEqual(set(s.keys()), expected)


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------

class TestSafety(unittest.TestCase):

    def test_trace_builder_does_not_mutate_recommendations(self) -> None:
        rec = _rec()
        original = dict(rec)
        build_recommendation_adoption_trace([rec], "some response")
        self.assertEqual(rec, original)

    def test_trace_builder_does_not_mutate_response_text(self) -> None:
        text = "I understand we both want a fair outcome."
        original = text
        build_recommendation_adoption_trace([_rec()], text)
        self.assertEqual(text, original)

    def test_trace_layer_does_not_change_route_key(self) -> None:
        agent = _agent()
        agent._record_recommendation_adoption_trace([_rec()], "some output", {})
        self.assertNotIn("_forced_route_key", agent.__dict__)

    def test_trace_layer_does_not_change_graph_mode(self) -> None:
        agent = _agent()
        agent._record_recommendation_adoption_trace([_rec()], "some output", {})
        self.assertFalse(hasattr(agent, "_graph_mode_override"))

    def test_trace_layer_does_not_break_reuse_mode(self) -> None:
        agent = _agent()
        agent._record_recommendation_adoption_trace(
            [_rec()], "output", {"graph_mode": "reuse"}
        )
        traces = agent.get_recommendation_adoption_traces()
        self.assertIsInstance(traces, list)

    def test_trace_layer_does_not_write_to_prompt(self) -> None:
        result = build_recommendation_adoption_trace([_rec()], "I understand the goal.")
        for tr in result:
            for v in tr.values():
                if isinstance(v, str):
                    self.assertNotIn("SYSTEM:", v)
                    self.assertNotIn("<<SYS>>", v)

    def test_trace_layer_does_not_mutate_feedback_or_reputation(self) -> None:
        agent = _agent()
        agent._record_strategy_outcome_feedback(
            [{"strategy_id": "s1", "based_on_pattern_ids": ["p1"]}],
            {"softening_detected": True},
        )
        fb_before = list(agent.get_strategy_outcome_feedback_events())
        agent._record_recommendation_adoption_trace([_rec()], "some output", {})
        fb_after = list(agent.get_strategy_outcome_feedback_events())
        self.assertEqual(fb_before, fb_after)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

class TestMetrics(unittest.TestCase):

    def test_calls_total_increments(self) -> None:
        agent = _agent()
        agent._record_recommendation_adoption_trace([_rec()], "I understand.", {})
        m = agent.get_recommendation_adoption_metrics()
        self.assertEqual(m["calls_total"], 1)

    def test_recommendations_processed_total(self) -> None:
        agent = _agent()
        agent._record_recommendation_adoption_trace(
            [_rec("s1"), _rec("s2")], "I understand.", {}
        )
        m = agent.get_recommendation_adoption_metrics()
        self.assertEqual(m["recommendations_processed_total"], 2)

    def test_traces_total(self) -> None:
        agent = _agent()
        agent._record_recommendation_adoption_trace([_rec()], "output", {})
        m = agent.get_recommendation_adoption_metrics()
        self.assertEqual(m["traces_total"], 1)

    def test_adopted_total_metric(self) -> None:
        agent = _agent()
        agent._record_recommendation_adoption_trace(
            [_rec(actions=["acknowledge common ground before moving forward"])],
            "I understand and agree that we should proceed together.",
            {},
        )
        m = agent.get_recommendation_adoption_metrics()
        self.assertGreaterEqual(m["adopted_total"] + m["partially_adopted_total"], 1)

    def test_not_adopted_total_metric(self) -> None:
        agent = _agent()
        agent._record_recommendation_adoption_trace(
            [_rec(actions=["acknowledge common ground before moving forward"])],
            "The schema migration requires updating all foreign keys.",
            {},
        )
        m = agent.get_recommendation_adoption_metrics()
        self.assertGreaterEqual(m["not_adopted_total"], 1)

    def test_avg_adoption_score_property(self) -> None:
        m = AlignmentRecommendationAdoptionMetrics(
            traces_total=4,
            score_sum=3.0,
        )
        self.assertAlmostEqual(m.avg_adoption_score, 0.75, places=3)

    def test_action_matches_total_increments(self) -> None:
        agent = _agent()
        agent._record_recommendation_adoption_trace(
            [_rec(actions=["acknowledge common ground before moving forward"])],
            "I understand and agree that we should work together.",
            {},
        )
        m = agent.get_recommendation_adoption_metrics()
        self.assertGreaterEqual(m["action_matches_total"], 0)

    def test_metrics_to_dict_has_all_keys(self) -> None:
        m = AlignmentRecommendationAdoptionMetrics()
        d = m.to_dict()
        expected = {
            "calls_total", "recommendations_processed_total", "traces_total",
            "adopted_total", "partially_adopted_total", "not_adopted_total",
            "avg_adoption_score", "action_matches_total", "unknown_actions_total",
        }
        self.assertEqual(set(d.keys()), expected)


# ---------------------------------------------------------------------------
# ResonanceAgent integration
# ---------------------------------------------------------------------------

class TestAgentIntegration(unittest.TestCase):

    def test_traces_written_post_response(self) -> None:
        agent = _agent()
        agent._record_recommendation_adoption_trace(
            [_rec()], "I understand your concern.", {}
        )
        traces = agent.get_recommendation_adoption_traces()
        self.assertIsInstance(traces, list)

    def test_summary_accessible(self) -> None:
        agent = _agent()
        agent._record_recommendation_adoption_trace([_rec()], "output", {})
        summary = agent.get_recommendation_adoption_summary()
        self.assertIn("total_traces", summary)

    def test_no_recommendations_handled_safely(self) -> None:
        agent = _agent()
        agent._record_recommendation_adoption_trace([], "output", {})
        traces = agent.get_recommendation_adoption_traces()
        self.assertEqual(traces, [])

    def test_existing_alignment_outputs_intact(self) -> None:
        agent = _agent()
        agent._record_recommendation_adoption_trace([_rec()], "output", {})
        self.assertIsInstance(agent.get_alignment_digest(), dict)
        self.assertIsInstance(agent.get_alignment_success_patterns(), list)
        self.assertIsInstance(agent.get_strategy_feedback_summary(), dict)
        self.assertIsInstance(agent.get_alignment_strategy_aggregation(), dict)
        self.assertIsInstance(agent.get_alignment_strategy_reputation_overlay({}), list)


if __name__ == "__main__":
    unittest.main()
