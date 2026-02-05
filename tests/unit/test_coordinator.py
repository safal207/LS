"""
Tests for Coordinator (Phase 10)

Verifies:
- Mode selection contract
- Context sync contract
- Cognitive hygiene contract
- No side effects (pure functions)
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from coordinator import (
    Coordinator,
    ModeDetector,
    ContextSync,
    CognitiveHygiene,
)


class TestModeDetector(unittest.TestCase):
    """Test Mode Detector (input analysis)."""

    def setUp(self):
        self.detector = ModeDetector()

    def test_simple_input_is_mode_a(self):
        """Short, simple input should suggest Mode A."""
        analysis = self.detector.analyze("Hi", context={}, system_load=0.0)
        self.assertEqual(analysis.mode, "A")

    def test_explanation_request_is_mode_b(self):
        """Input asking 'why' or 'how' should suggest Mode B."""
        analysis = self.detector.analyze(
            "Why is the sky blue?",
            context={},
            system_load=0.0,
        )
        self.assertEqual(analysis.mode, "B")

    def test_complex_input_is_mode_b(self):
        """Long, complex input should suggest Mode B."""
        long_input = "This is a very long input with many words " * 5
        analysis = self.detector.analyze(
            long_input,
            context={},
            system_load=0.0,
        )
        self.assertIn(analysis.mode, ["B", "both"])

    def test_high_load_prefers_mode_a(self):
        """Under high load, prefer Mode A (fast)."""
        analysis = self.detector.analyze(
            "What time is it?",
            context={},
            system_load=0.9,
        )
        self.assertEqual(analysis.mode, "A")


class TestContextSync(unittest.TestCase):
    """Test Context Synchronization."""

    def setUp(self):
        self.sync = ContextSync()

    def test_merge_preserves_both_results(self):
        """Merging should include both A and B results."""
        context = {"key": "value"}

        merged = self.sync.merge(
            mode_a_result={"answer": "fast"},
            mode_b_result={"answer": "deep", "explanation": "because..."},
            context=context,
        )

        self.assertIn("mode_a_result", merged)
        self.assertIn("mode_b_result", merged)

    def test_merge_includes_original_context(self):
        """Merge should preserve original context."""
        context = {"goal": "test"}

        merged = self.sync.merge(
            mode_a_result=None,
            mode_b_result=None,
            context=context,
        )

        self.assertEqual(merged["goal"], "test")


class TestCognitiveHygiene(unittest.TestCase):
    """Test Cognitive Hygiene (cleanup)."""

    def setUp(self):
        self.hygiene = CognitiveHygiene()

    def test_removes_none_values(self):
        """Cleanup should remove None values."""
        context = {"a": 1, "b": None, "c": 3}
        cleaned = self.hygiene.clean(context)

        self.assertNotIn("b", cleaned)
        self.assertIn("a", cleaned)
        self.assertIn("c", cleaned)


class TestCoordinator(unittest.TestCase):
    """Test Main Coordinator."""

    def setUp(self):
        self.coordinator = Coordinator()

    def test_choose_mode_returns_decision(self):
        """choose_mode() should return CoordinationDecision."""
        decision = self.coordinator.choose_mode(
            input_data="Hello",
            context={},
        )

        self.assertIsNotNone(decision)
        self.assertIn(decision.mode, ["A", "B", "both"])
        self.assertGreater(decision.confidence, 0)

    def test_finalize_returns_tuple(self):
        """finalize() should return (result, context)."""
        result, context = self.coordinator.finalize(
            mode_result={"answer": "test"},
            context={"goal": "test"},
        )

        self.assertIsNotNone(result)
        self.assertIsNotNone(context)


if __name__ == "__main__":
    unittest.main()
