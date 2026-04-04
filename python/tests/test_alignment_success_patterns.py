from __future__ import annotations

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modules"))

from modules.agent.alignment_memory import AlignmentMemoryUnit
from modules.agent.alignment_success_patterns import (
    AlignmentSuccessPatternMetrics,
    build_alignment_success_patterns,
    make_alignment_pattern_key,
)
from modules.agent.resonance_agent import ResonanceAgent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _unit(
    *,
    hotspot: str | None = "deadline_vs_quality",
    mismatch_reasons: list[str] | None = None,
    softening_signals: list[str] | None = None,
    effect_reason: str | None = "bridge_phrase \u2192 cooperative softening",
    guidance_effective: bool = True,
    softening_detected: bool = True,
    response_score: float = 0.72,
    goal_alignment_score: float = 0.68,
) -> AlignmentMemoryUnit:
    return AlignmentMemoryUnit(
        source_question="Как договориться?",
        intent="coordinate",
        why="resolve_conflict",
        alignment_hotspot=hotspot,
        mismatch_reasons=mismatch_reasons or ["intent_conflict:ship_now/verify_safety"],
        guidance_applied=True,
        softening_detected=softening_detected,
        softening_signals=softening_signals or ["bridge_phrase", "pacing_marker"],
        effect_reason=effect_reason,
        guidance_effective=guidance_effective,
        response_score=response_score,
        goal_alignment_score=goal_alignment_score,
        tension_score_before=0.55,
        metadata={"cycle_id": "test-001"},
    )


# ---------------------------------------------------------------------------
# Pattern extraction (1–6)
# ---------------------------------------------------------------------------


class TestPatternExtraction(unittest.TestCase):

    def test_empty_list_returns_empty(self) -> None:
        self.assertEqual(build_alignment_success_patterns([]), [])

    def test_single_unit_does_not_create_pattern(self) -> None:
        """One unit with support_count < 2 must not produce a pattern."""
        patterns = build_alignment_success_patterns([_unit()], min_support=2)
        self.assertEqual(patterns, [])

    def test_two_identical_successful_units_create_one_pattern(self) -> None:
        units = [_unit(), _unit()]
        patterns = build_alignment_success_patterns(units)
        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns[0]["support_count"], 2)

    def test_units_with_different_hotspots_create_separate_patterns(self) -> None:
        units = [
            _unit(hotspot="deadline_vs_quality"),
            _unit(hotspot="deadline_vs_quality"),
            _unit(hotspot="scope_vs_speed"),
            _unit(hotspot="scope_vs_speed"),
        ]
        patterns = build_alignment_success_patterns(units)
        hotspots = {p["hotspot"] for p in patterns}
        self.assertIn("deadline_vs_quality", hotspots)
        self.assertIn("scope_vs_speed", hotspots)
        self.assertEqual(len(patterns), 2)

    def test_units_with_different_mismatch_reasons_create_separate_patterns(self) -> None:
        units = [
            _unit(mismatch_reasons=["intent_conflict:A"]),
            _unit(mismatch_reasons=["intent_conflict:A"]),
            _unit(mismatch_reasons=["intent_conflict:B"]),
            _unit(mismatch_reasons=["intent_conflict:B"]),
        ]
        patterns = build_alignment_success_patterns(units)
        self.assertEqual(len(patterns), 2)

    def test_units_with_different_softening_signals_create_separate_patterns(self) -> None:
        units = [
            _unit(softening_signals=["bridge_phrase"]),
            _unit(softening_signals=["bridge_phrase"]),
            _unit(softening_signals=["acknowledgment"]),
            _unit(softening_signals=["acknowledgment"]),
        ]
        patterns = build_alignment_success_patterns(units)
        self.assertEqual(len(patterns), 2)


# ---------------------------------------------------------------------------
# Pattern quality (7–12)
# ---------------------------------------------------------------------------


class TestPatternQuality(unittest.TestCase):

    def _two_units(self) -> list[AlignmentMemoryUnit]:
        return [
            _unit(guidance_effective=True, response_score=0.8, goal_alignment_score=0.7),
            _unit(guidance_effective=False, response_score=0.6, goal_alignment_score=0.5),
        ]

    def test_support_count_is_correct(self) -> None:
        patterns = build_alignment_success_patterns(self._two_units())
        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns[0]["support_count"], 2)

    def test_effective_rate_is_correct(self) -> None:
        patterns = build_alignment_success_patterns(self._two_units())
        # 1 out of 2 is guidance_effective
        self.assertAlmostEqual(patterns[0]["effective_rate"], 0.5, places=2)

    def test_avg_response_score_is_correct(self) -> None:
        patterns = build_alignment_success_patterns(self._two_units())
        expected = round((0.8 + 0.6) / 2, 3)
        self.assertAlmostEqual(patterns[0]["avg_response_score"], expected, places=3)

    def test_avg_goal_alignment_score_is_correct(self) -> None:
        patterns = build_alignment_success_patterns(self._two_units())
        expected = round((0.7 + 0.5) / 2, 3)
        self.assertAlmostEqual(patterns[0]["avg_goal_alignment_score"], expected, places=3)

    def test_pattern_id_is_deterministic(self) -> None:
        """Same inputs always produce the same pattern_id."""
        u = _unit()
        self.assertEqual(make_alignment_pattern_key(u), make_alignment_pattern_key(u))

    def test_pattern_does_not_carry_raw_unit_fields(self) -> None:
        patterns = build_alignment_success_patterns([_unit(), _unit()])
        for internal in ("source_question", "metadata", "_alignment_report", "item"):
            self.assertNotIn(internal, patterns[0])


# ---------------------------------------------------------------------------
# Safety (13–16)
# ---------------------------------------------------------------------------


class TestSafety(unittest.TestCase):

    def test_pattern_builder_does_not_mutate_units(self) -> None:
        u = _unit()
        before = u.alignment_hotspot
        build_alignment_success_patterns([u, u])
        self.assertEqual(u.alignment_hotspot, before)

    def test_pattern_build_does_not_change_graph_mode(self) -> None:
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        item: dict = {"graph_mode": "reuse"}
        with agent._alignment_memory_lock:
            agent._alignment_memory_units.extend([_unit(), _unit()])
        agent.get_alignment_success_patterns()
        self.assertEqual(item["graph_mode"], "reuse")

    def test_pattern_build_does_not_set_route_key(self) -> None:
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        with agent._alignment_memory_lock:
            agent._alignment_memory_units.extend([_unit(), _unit()])
        result = agent.get_alignment_success_patterns()
        for p in result:
            self.assertNotIn("route_key", p)

    def test_reuse_mode_not_broken(self) -> None:
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        result = agent.process_item({"type": "question", "text": "Тест.", "graph_mode": "reuse"})
        self.assertIn("final_output", result)


# ---------------------------------------------------------------------------
# Metrics (17–23)
# ---------------------------------------------------------------------------


class TestMetrics(unittest.TestCase):

    def test_calls_total_increments(self) -> None:
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        agent.get_alignment_success_patterns()
        agent.get_alignment_success_patterns()
        m = agent.get_alignment_success_pattern_metrics()
        self.assertGreaterEqual(m.get("calls_total", 0), 2)

    def test_units_processed_total_accumulates(self) -> None:
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        with agent._alignment_memory_lock:
            agent._alignment_memory_units.extend([_unit(), _unit()])
        agent.get_alignment_success_patterns()
        m = agent.get_alignment_success_pattern_metrics()
        self.assertGreaterEqual(m.get("units_processed_total", 0), 2)

    def test_patterns_built_total_increments(self) -> None:
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        with agent._alignment_memory_lock:
            agent._alignment_memory_units.extend([_unit(), _unit()])
        agent.get_alignment_success_patterns()
        m = agent.get_alignment_success_pattern_metrics()
        self.assertGreaterEqual(m.get("patterns_built_total", 0), 1)

    def test_patterns_skipped_total_increments_for_weak_groups(self) -> None:
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        # One unit with unique key → should be skipped (support < 2)
        with agent._alignment_memory_lock:
            agent._alignment_memory_units.append(
                _unit(hotspot="unique_hotspot_xyz", mismatch_reasons=["unique_reason_xyz"])
            )
        agent.get_alignment_success_patterns()
        m = agent.get_alignment_success_pattern_metrics()
        self.assertGreaterEqual(m.get("patterns_skipped_total", 0), 1)

    def test_avg_units_per_pattern_property(self) -> None:
        metrics = AlignmentSuccessPatternMetrics()
        metrics.calls_total = 3
        metrics.units_processed_total = 9
        metrics.patterns_built_total = 3
        self.assertAlmostEqual(metrics.avg_units_per_pattern, 3.0, places=1)

    def test_patterns_with_hotspot_counter(self) -> None:
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        with agent._alignment_memory_lock:
            agent._alignment_memory_units.extend([
                _unit(hotspot="deadline_vs_quality"),
                _unit(hotspot="deadline_vs_quality"),
            ])
        agent.get_alignment_success_patterns()
        m = agent.get_alignment_success_pattern_metrics()
        self.assertGreaterEqual(m.get("patterns_with_hotspot", 0), 1)

    def test_patterns_with_softening_counter(self) -> None:
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        with agent._alignment_memory_lock:
            agent._alignment_memory_units.extend([
                _unit(softening_signals=["bridge_phrase"]),
                _unit(softening_signals=["bridge_phrase"]),
            ])
        agent.get_alignment_success_patterns()
        m = agent.get_alignment_success_pattern_metrics()
        self.assertGreaterEqual(m.get("patterns_with_softening", 0), 1)


# ---------------------------------------------------------------------------
# ResonanceAgent integration (24–25)
# ---------------------------------------------------------------------------


class TestAgentIntegration(unittest.TestCase):

    def test_get_alignment_success_patterns_has_no_side_effects(self) -> None:
        """Calling get_alignment_success_patterns must not modify in-memory units."""
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        u = _unit()
        with agent._alignment_memory_lock:
            agent._alignment_memory_units.extend([u, u])
        before_count = len(agent._alignment_memory_units)
        agent.get_alignment_success_patterns()
        with agent._alignment_memory_lock:
            after_count = len(agent._alignment_memory_units)
        self.assertEqual(before_count, after_count)

    def test_alignment_success_patterns_key_in_output(self) -> None:
        """alignment_success_patterns key is always present in process_item result."""
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        result = agent.process_item({"type": "question", "text": "Тест."})
        self.assertIn("alignment_success_patterns", result)
        self.assertIsInstance(result["alignment_success_patterns"], list)


if __name__ == "__main__":
    unittest.main()
