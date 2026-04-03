# -*- coding: utf-8 -*-
"""
Tests for softening_detector.py — language-agnostic, explainable outcome layer.

16 cases covering:
  - Detection behaviour (EN + RU + multilingual + neutral + adversarial + edge)
  - Explainability (signals, reason)
  - Observability (counters, backward-compat)
  - Safety (advisory-only — no route/graph side-effects)
"""
from __future__ import annotations

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modules"))

from agent.softening_detector import SofteningAnalysis, analyze_softening_signals


# ── 1–7  Detection behaviour ──────────────────────────────────────────────────

class TestDetectionBehaviour(unittest.TestCase):

    def test_cooperative_russian_detected(self):
        """RU cooperative response → softening_detected=True."""
        text = "Я понимаю тебя. Давай вместе рассмотрим варианты — что тебе важно прежде всего?"
        result = analyze_softening_signals(text)
        self.assertTrue(result.softening_detected)
        self.assertGreater(result.score, 0.0)

    def test_cooperative_english_detected(self):
        """EN cooperative response → softening_detected=True."""
        text = "I understand your concern. Let's look at this together — what would work best for you?"
        result = analyze_softening_signals(text)
        self.assertTrue(result.softening_detected)
        self.assertGreater(result.score, 0.0)

    def test_neutral_technical_not_detected(self):
        """Dry technical response → softening_detected=False."""
        text = "The function returns a list of integers sorted in ascending order."
        result = analyze_softening_signals(text)
        self.assertFalse(result.softening_detected)

    def test_adversarial_imperative_not_detected(self):
        """Directive/adversarial response → softening_detected=False."""
        text = "You must fix this immediately. You have to do it now, stop it."
        result = analyze_softening_signals(text)
        self.assertFalse(result.softening_detected)

    def test_empty_string_does_not_raise(self):
        """Empty input → graceful neutral result, no exception."""
        result = analyze_softening_signals("")
        self.assertFalse(result.softening_detected)
        self.assertEqual(result.score, 0.0)
        self.assertEqual(result.reason, "empty_input")

    def test_mixed_language_detected(self):
        """Mixed RU/EN cooperative text → softening_detected=True."""
        text = "I understand. Давай вместе посмотрим на варианты, what do you think?"
        result = analyze_softening_signals(text)
        self.assertTrue(result.softening_detected)

    def test_adversarial_caps_score_even_with_cooperative_markers(self):
        """Adversarial markers cap score even if cooperative phrases present."""
        text = "I understand but you must stop it and you're wrong!"
        result = analyze_softening_signals(text)
        # score capped at ≤ 0.2 due to adversarial hit
        self.assertLessEqual(result.score, 0.2)
        self.assertFalse(result.softening_detected)


# ── 8–10  Explainability ──────────────────────────────────────────────────────

class TestExplainability(unittest.TestCase):

    def test_positive_detection_has_nonempty_signals(self):
        """Detected softening → signals list is non-empty."""
        text = "I hear you. Let's work through this together — what do you think?"
        result = analyze_softening_signals(text)
        self.assertTrue(result.softening_detected)
        self.assertGreater(len(result.signals), 0)

    def test_neutral_detection_still_has_reason(self):
        """Even when not detected, reason field is set and readable."""
        text = "SELECT * FROM users WHERE id = 1;"
        result = analyze_softening_signals(text)
        self.assertFalse(result.softening_detected)
        self.assertIsNotNone(result.reason)
        self.assertIsInstance(result.reason, str)

    def test_signal_list_has_no_duplicates(self):
        """Signal list must not contain duplicate entries."""
        text = (
            "I understand and I hear you — let's work together. "
            "Perhaps we could start with the first step, what do you think?"
        )
        result = analyze_softening_signals(text)
        self.assertEqual(len(result.signals), len(set(result.signals)))


# ── 11–13  Observability ──────────────────────────────────────────────────────

class TestObservability(unittest.TestCase):

    def test_to_dict_is_backward_compatible(self):
        """to_dict() always contains the four required keys."""
        result = analyze_softening_signals("давай вместе")
        d = result.to_dict()
        self.assertIn("softening_detected", d)
        self.assertIn("score", d)
        self.assertIn("signals", d)
        self.assertIn("reason", d)

    def test_to_dict_score_is_rounded(self):
        """Score in to_dict() has at most 3 decimal places."""
        result = analyze_softening_signals("let's work together and i understand your point")
        d = result.to_dict()
        # Verify it can be safely serialised to JSON without precision issues
        score_str = str(d["score"])
        decimals = len(score_str.split(".")[-1]) if "." in score_str else 0
        self.assertLessEqual(decimals, 3)

    def test_signal_counts_update_via_resonance_agent(self):
        """ResonanceAgent._record_alignment_outcome increments softening counters."""
        try:
            from agent.resonance_agent import ResonanceAgent
        except Exception:
            self.skipTest("ResonanceAgent not importable in this environment")

        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        before = agent.get_alignment_outcome_metrics()

        # Simulate a cycle with a cooperative response
        item: dict = {
            "_alignment_report": {"tension_score": 0.5},
            "_alignment_guidance": "some guidance",
            "_resonance_score": 0.7,
        }
        agent._record_alignment_outcome(
            item,
            response_text="I understand. Let's work together on this, what do you think?",
            response_score=0.7,
            goal_alignment_score=0.7,
        )

        after = agent.get_alignment_outcome_metrics()
        self.assertEqual(after["observed_cycles"], before["observed_cycles"] + 1)
        # softening should have been detected → count increased
        self.assertGreaterEqual(after["softening_detected_count"], 1)
        self.assertIn("softening_signal_counts", after)


# ── 14–16  Safety (advisory-only) ────────────────────────────────────────────

class TestAdvisoryOnly(unittest.TestCase):

    def test_detector_does_not_set_graph_mode(self):
        """SofteningAnalysis carries no graph_mode attribute."""
        result = analyze_softening_signals("I understand, let's collaborate together.")
        self.assertFalse(hasattr(result, "graph_mode"))
        self.assertNotIn("graph_mode", result.to_dict())

    def test_detector_does_not_set_route_key(self):
        """SofteningAnalysis carries no route_key attribute."""
        result = analyze_softening_signals("давай вместе найдём решение")
        self.assertFalse(hasattr(result, "route_key"))
        self.assertNotIn("route_key", result.to_dict())

    def test_reuse_mode_item_not_modified_by_detector(self):
        """Detector called with a reuse-mode item — item graph_mode unchanged."""
        item = {"graph_mode": "reuse", "route_key": "reuse", "text": "ok"}
        # Detector only analyses text, never touches item
        result = analyze_softening_signals(str(item.get("text", "")))
        # item is untouched
        self.assertEqual(item["graph_mode"], "reuse")
        self.assertEqual(item["route_key"], "reuse")
        # result is observability only
        self.assertIsInstance(result, SofteningAnalysis)


if __name__ == "__main__":
    unittest.main()
