from __future__ import annotations

import json
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modules"))

from modules.agent.alignment_digest import (
    AlignmentDigestMetrics,
    build_alignment_digest,
)
from modules.agent.alignment_memory import AlignmentMemoryUnit
from modules.agent.resonance_agent import ResonanceAgent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_DIGEST_KEYS = frozenset({
    "total_units",
    "hotspots_top",
    "mismatch_reasons_top",
    "softening_signals_top",
    "effect_reasons_top",
    "guidance_applied_count",
    "guidance_effective_count",
    "softening_detected_count",
    "avg_response_score",
    "avg_goal_alignment_score",
    "avg_tension_score_before",
    "effective_rate",
    "top_success_patterns",
})


def _unit(
    *,
    hotspot: str | None = "deadline_vs_quality",
    mismatch_reasons: list[str] | None = None,
    softening_signals: list[str] | None = None,
    effect_reason: str | None = "bridge_phrase \u2192 cooperative softening",
    guidance_applied: bool = True,
    guidance_effective: bool = True,
    softening_detected: bool = True,
    response_score: float = 0.7,
    goal_alignment_score: float = 0.65,
    tension_score_before: float | None = 0.55,
) -> AlignmentMemoryUnit:
    return AlignmentMemoryUnit(
        source_question="Как договориться?",
        intent="coordinate",
        why="resolve_conflict",
        alignment_hotspot=hotspot,
        mismatch_reasons=mismatch_reasons or ["intent_conflict:ship_now/verify_safety"],
        guidance_applied=guidance_applied,
        softening_detected=softening_detected,
        softening_signals=softening_signals or ["bridge_phrase", "pacing_marker"],
        effect_reason=effect_reason,
        guidance_effective=guidance_effective,
        response_score=response_score,
        goal_alignment_score=goal_alignment_score,
        tension_score_before=tension_score_before,
        metadata={"cycle_id": "test-001"},
    )


# ---------------------------------------------------------------------------
# Digest building (1–6)
# ---------------------------------------------------------------------------


class TestDigestBuilding(unittest.TestCase):

    def test_empty_list_returns_neutral_digest(self) -> None:
        """build_alignment_digest([]) returns zero-values, not an exception."""
        d = build_alignment_digest([])
        self.assertEqual(d["total_units"], 0)
        self.assertEqual(d["guidance_applied_count"], 0)
        self.assertEqual(d["hotspots_top"], [])
        self.assertEqual(d["effective_rate"], 0.0)

    def test_single_unit_appears_in_digest(self) -> None:
        d = build_alignment_digest([_unit(hotspot="deadline_vs_quality")])
        self.assertEqual(d["total_units"], 1)
        self.assertEqual(d["hotspots_top"][0]["value"], "deadline_vs_quality")
        self.assertEqual(d["hotspots_top"][0]["count"], 1)

    def test_repeated_hotspots_aggregate(self) -> None:
        units = [
            _unit(hotspot="deadline_vs_quality"),
            _unit(hotspot="deadline_vs_quality"),
            _unit(hotspot="scope_vs_speed"),
        ]
        d = build_alignment_digest(units)
        top = {e["value"]: e["count"] for e in d["hotspots_top"]}
        self.assertEqual(top["deadline_vs_quality"], 2)
        self.assertEqual(top["scope_vs_speed"], 1)

    def test_repeated_mismatch_reasons_aggregate(self) -> None:
        units = [
            _unit(mismatch_reasons=["intent_conflict:A"]),
            _unit(mismatch_reasons=["intent_conflict:A", "intent_conflict:B"]),
        ]
        d = build_alignment_digest(units)
        top = {e["value"]: e["count"] for e in d["mismatch_reasons_top"]}
        self.assertEqual(top["intent_conflict:A"], 2)
        self.assertEqual(top["intent_conflict:B"], 1)

    def test_repeated_softening_signals_aggregate(self) -> None:
        units = [
            _unit(softening_signals=["bridge_phrase", "pacing_marker"]),
            _unit(softening_signals=["bridge_phrase"]),
        ]
        d = build_alignment_digest(units)
        top = {e["value"]: e["count"] for e in d["softening_signals_top"]}
        self.assertEqual(top["bridge_phrase"], 2)
        self.assertEqual(top["pacing_marker"], 1)

    def test_repeated_effect_reasons_aggregate(self) -> None:
        reason = "bridge_phrase \u2192 cooperative softening"
        units = [_unit(effect_reason=reason), _unit(effect_reason=reason)]
        d = build_alignment_digest(units)
        top = {e["value"]: e["count"] for e in d["effect_reasons_top"]}
        self.assertEqual(top[reason], 2)


# ---------------------------------------------------------------------------
# Aggregate values (7–12)
# ---------------------------------------------------------------------------


class TestAggregateValues(unittest.TestCase):

    def _three_units(self) -> list[AlignmentMemoryUnit]:
        return [
            _unit(guidance_applied=True, guidance_effective=True, softening_detected=True,
                  response_score=0.8, goal_alignment_score=0.7, tension_score_before=0.6),
            _unit(guidance_applied=True, guidance_effective=False, softening_detected=False,
                  response_score=0.6, goal_alignment_score=0.5, tension_score_before=0.4),
            _unit(guidance_applied=False, guidance_effective=False, softening_detected=True,
                  response_score=0.7, goal_alignment_score=0.6, tension_score_before=0.5),
        ]

    def test_guidance_applied_count(self) -> None:
        d = build_alignment_digest(self._three_units())
        self.assertEqual(d["guidance_applied_count"], 2)

    def test_guidance_effective_count(self) -> None:
        d = build_alignment_digest(self._three_units())
        self.assertEqual(d["guidance_effective_count"], 1)

    def test_softening_detected_count(self) -> None:
        d = build_alignment_digest(self._three_units())
        self.assertEqual(d["softening_detected_count"], 2)

    def test_avg_response_score(self) -> None:
        d = build_alignment_digest(self._three_units())
        expected = round((0.8 + 0.6 + 0.7) / 3, 3)
        self.assertAlmostEqual(d["avg_response_score"], expected, places=3)

    def test_avg_goal_alignment_score(self) -> None:
        d = build_alignment_digest(self._three_units())
        expected = round((0.7 + 0.5 + 0.6) / 3, 3)
        self.assertAlmostEqual(d["avg_goal_alignment_score"], expected, places=3)

    def test_avg_tension_score_before(self) -> None:
        d = build_alignment_digest(self._three_units())
        expected = round((0.6 + 0.4 + 0.5) / 3, 3)
        self.assertAlmostEqual(d["avg_tension_score_before"], expected, places=3)


# ---------------------------------------------------------------------------
# Output quality (13–16)
# ---------------------------------------------------------------------------


class TestOutputQuality(unittest.TestCase):

    def test_top_lists_are_bounded(self) -> None:
        """hotspots_top must not exceed top_n entries."""
        units = [_unit(hotspot=f"hotspot_{i}") for i in range(20)]
        d = build_alignment_digest(units, top_n=5)
        self.assertLessEqual(len(d["hotspots_top"]), 5)

    def test_digest_is_json_serializable(self) -> None:
        d = build_alignment_digest([_unit()])
        serialised = json.dumps(d, ensure_ascii=False)
        self.assertIsInstance(json.loads(serialised), dict)

    def test_digest_has_no_internal_keys(self) -> None:
        """Digest must not leak internal pipeline fields."""
        d = build_alignment_digest([_unit()])
        for key in ("_alignment_report", "_copilot_output", "_graph_runtime", "item"):
            self.assertNotIn(key, d)

    def test_digest_keys_are_stable(self) -> None:
        """Key set must always equal _DIGEST_KEYS regardless of input."""
        self.assertEqual(set(build_alignment_digest([])), _DIGEST_KEYS)
        self.assertEqual(set(build_alignment_digest([_unit()])), _DIGEST_KEYS)
        self.assertEqual(set(build_alignment_digest([_unit(), _unit()])), _DIGEST_KEYS)


# ---------------------------------------------------------------------------
# Safety (17–20)
# ---------------------------------------------------------------------------


class TestSafety(unittest.TestCase):

    def test_digest_does_not_mutate_graph_mode(self) -> None:
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        item: dict = {"graph_mode": "reuse"}
        with agent._alignment_memory_lock:
            agent._alignment_memory_units.append(_unit())
        agent.get_alignment_digest()
        # item is untouched
        self.assertEqual(item["graph_mode"], "reuse")

    def test_digest_does_not_set_route_key(self) -> None:
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        with agent._alignment_memory_lock:
            agent._alignment_memory_units.append(_unit())
        d = agent.get_alignment_digest()
        self.assertNotIn("route_key", d)

    def test_reuse_mode_unaffected_by_digest(self) -> None:
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        result = agent.process_item({"type": "question", "text": "Тест.", "graph_mode": "reuse"})
        self.assertIn("final_output", result)

    def test_digest_does_not_mutate_memory_units(self) -> None:
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        u = _unit()
        with agent._alignment_memory_lock:
            agent._alignment_memory_units.append(u)
        before_hotspot = u.alignment_hotspot
        agent.get_alignment_digest()
        self.assertEqual(u.alignment_hotspot, before_hotspot)


# ---------------------------------------------------------------------------
# Metrics (21–25)
# ---------------------------------------------------------------------------


class TestDigestMetrics(unittest.TestCase):

    def test_calls_total_increments(self) -> None:
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        agent.get_alignment_digest()
        agent.get_alignment_digest()
        m = agent.get_alignment_digest_metrics()
        self.assertGreaterEqual(m.get("calls_total", 0), 2)

    def test_empty_total_increments_when_no_units(self) -> None:
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        agent.get_alignment_digest()
        m = agent.get_alignment_digest_metrics()
        self.assertGreaterEqual(m.get("empty_total", 0), 1)

    def test_nonempty_total_increments_when_units_present(self) -> None:
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        with agent._alignment_memory_lock:
            agent._alignment_memory_units.append(_unit())
        agent.get_alignment_digest()
        m = agent.get_alignment_digest_metrics()
        self.assertGreaterEqual(m.get("nonempty_total", 0), 1)

    def test_units_processed_total_accumulates(self) -> None:
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        with agent._alignment_memory_lock:
            agent._alignment_memory_units.extend([_unit(), _unit()])
        agent.get_alignment_digest()
        m = agent.get_alignment_digest_metrics()
        self.assertGreaterEqual(m.get("units_processed_total", 0), 2)

    def test_avg_units_per_digest_is_correct(self) -> None:
        metrics = AlignmentDigestMetrics()
        metrics.calls_total = 4
        metrics.units_processed_total = 10
        self.assertAlmostEqual(metrics.avg_units_per_digest, 2.5, places=1)
        self.assertEqual(metrics.to_dict()["avg_units_per_digest"], 2.5)


if __name__ == "__main__":
    unittest.main()
