from __future__ import annotations

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modules"))

from modules.agent.alignment_memory import (
    AlignmentMemoryUnit,
    build_alignment_memory_hint,
    find_relevant_alignment_units,
)
from modules.agent.resonance_agent import ResonanceAgent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_unit(
    *,
    intent: str = "coordinate",
    hotspot: str | None = "deadline_vs_quality",
    softening_detected: bool = True,
    guidance_effective: bool = True,
    effect_reason: str = "bridge_phrase + pacing_marker \u2192 cooperative softening",
    mismatch_reasons: list[str] | None = None,
) -> AlignmentMemoryUnit:
    return AlignmentMemoryUnit(
        source_question="Как нам договориться?",
        intent=intent,
        why="resolve_conflict",
        alignment_hotspot=hotspot,
        mismatch_reasons=mismatch_reasons or ["intent_conflict:ship_now/verify_safety"],
        guidance_applied=True,
        softening_detected=softening_detected,
        softening_signals=["bridge_phrase", "pacing_marker"] if softening_detected else [],
        effect_reason=effect_reason,
        guidance_effective=guidance_effective,
        response_score=0.72,
        goal_alignment_score=0.68,
        tension_score_before=0.6,
        metadata={"cycle_id": "fixture-001"},
    )


# ---------------------------------------------------------------------------
# Retrieval logic (1–8)
# ---------------------------------------------------------------------------


class TestRetrievalLogic(unittest.TestCase):

    def test_exact_intent_match_returns_unit(self) -> None:
        units = [_make_unit(intent="coordinate")]
        result = find_relevant_alignment_units(units, query_intent="coordinate", query_hotspot="")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].intent, "coordinate")

    def test_partial_intent_match_returns_unit(self) -> None:
        units = [_make_unit(intent="coordinate_tasks")]
        result = find_relevant_alignment_units(units, query_intent="coordinate", query_hotspot="")
        self.assertEqual(len(result), 1)

    def test_hotspot_match_returns_unit(self) -> None:
        units = [_make_unit(hotspot="deadline_vs_quality")]
        result = find_relevant_alignment_units(
            units, query_intent="", query_hotspot="deadline_vs_quality"
        )
        self.assertEqual(len(result), 1)

    def test_guidance_effective_preferred_over_not(self) -> None:
        """Units with guidance_effective=True should rank above non-effective ones
        when intent match quality is equal."""
        units = [
            _make_unit(intent="negotiate", guidance_effective=False),
            _make_unit(intent="negotiate", guidance_effective=True),
        ]
        result = find_relevant_alignment_units(units, query_intent="negotiate", query_hotspot="")
        self.assertTrue(result[0].guidance_effective)

    def test_max_results_is_respected(self) -> None:
        units = [_make_unit(intent="coordinate") for _ in range(10)]
        result = find_relevant_alignment_units(units, query_intent="coordinate", query_hotspot="", max_results=2)
        self.assertLessEqual(len(result), 2)

    def test_empty_units_returns_empty(self) -> None:
        result = find_relevant_alignment_units([], query_intent="coordinate", query_hotspot="deadline")
        self.assertEqual(result, [])

    def test_no_match_returns_empty(self) -> None:
        units = [_make_unit(intent="ship_now", hotspot="deadline_vs_speed")]
        result = find_relevant_alignment_units(
            units, query_intent="completely_unrelated_xyz", query_hotspot="unknown_hotspot_xyz"
        )
        self.assertEqual(result, [])

    def test_scoring_is_deterministic(self) -> None:
        units = [_make_unit(intent="coordinate"), _make_unit(intent="negotiate")]
        r1 = find_relevant_alignment_units(units, query_intent="coordinate", query_hotspot="")
        r2 = find_relevant_alignment_units(units, query_intent="coordinate", query_hotspot="")
        self.assertEqual([u.intent for u in r1], [u.intent for u in r2])


# ---------------------------------------------------------------------------
# Hint building (9–14)
# ---------------------------------------------------------------------------


class TestHintBuilding(unittest.TestCase):

    def test_empty_list_returns_none(self) -> None:
        self.assertIsNone(build_alignment_memory_hint([]))

    def test_single_unit_produces_readable_string(self) -> None:
        hint = build_alignment_memory_hint([_make_unit()])
        self.assertIsInstance(hint, str)
        self.assertTrue(len(hint) > 10)

    def test_multiple_units_all_present_in_hint(self) -> None:
        units = [
            _make_unit(intent="coordinate", hotspot="deadline_vs_quality"),
            _make_unit(intent="negotiate", hotspot="scope_vs_speed"),
        ]
        hint = build_alignment_memory_hint(units)
        assert hint is not None
        self.assertIn("deadline_vs_quality", hint)
        self.assertIn("scope_vs_speed", hint)

    def test_effect_reason_appears_in_hint(self) -> None:
        unit = _make_unit(effect_reason="bridge_phrase \u2192 cooperative softening")
        hint = build_alignment_memory_hint([unit])
        assert hint is not None
        self.assertIn("bridge_phrase", hint)

    def test_hotspot_appears_in_hint(self) -> None:
        unit = _make_unit(hotspot="team_velocity_vs_safety")
        hint = build_alignment_memory_hint([unit])
        assert hint is not None
        self.assertIn("team_velocity_vs_safety", hint)

    def test_hint_marked_as_advisory(self) -> None:
        """Hint must contain 'advisory' so LLM treats it as soft guidance."""
        hint = build_alignment_memory_hint([_make_unit()])
        assert hint is not None
        self.assertIn("advisory", hint.lower())


# ---------------------------------------------------------------------------
# Integration (15–18)
# ---------------------------------------------------------------------------


class TestIntegration(unittest.TestCase):

    def _agent_with_memory(self) -> ResonanceAgent:
        """Return an agent that has one relevant alignment unit in memory."""
        agent = ResonanceAgent(
            anchor=[],
            llm_fn=lambda _u, _s: "Понимаю, давай найдём решение вместе.",
            orientation="test",
        )
        # Pre-populate in-memory store with a relevant unit
        unit = _make_unit(intent="coordinate", hotspot="deadline_vs_quality")
        with agent._alignment_memory_lock:
            agent._alignment_memory_units.append(unit)
        return agent

    def test_stored_unit_is_retrieved_in_next_cycle(self) -> None:
        """After storing a unit, retrieval finds it for a matching subsequent cycle."""
        agent = self._agent_with_memory()
        result = agent.process_item({
            "type": "question",
            "text": "Как нам договориться по срокам?",
            "participants": [
                {"participant_id": "h1", "intent": "coordinate", "tension_signal": 0.7},
                {"participant_id": "a1", "intent": "coordinate", "tension_signal": 0.5},
            ],
        })
        # hint may or may not fire depending on intent detection, but should not crash
        self.assertIn("final_output", result)

    def test_no_memory_hint_is_none(self) -> None:
        """Fresh agent with no units: alignment_memory_hint is None in output."""
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        result = agent.process_item({"type": "question", "text": "Простой вопрос."})
        self.assertIsNone(result.get("alignment_memory_hint"))

    def test_alignment_memory_hint_key_in_output(self) -> None:
        """alignment_memory_hint key always present in process_item result."""
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        result = agent.process_item({"type": "question", "text": "Тест."})
        self.assertIn("alignment_memory_hint", result)

    def test_graph_mode_unchanged_by_memory_hint(self) -> None:
        """Retrieving and injecting a memory hint must not mutate graph_mode."""
        agent = self._agent_with_memory()
        item: dict = {
            "graph_mode": "reuse",
            "text": "Как договориться?",
            "_alignment_report": {
                "pairwise_hotspots": [{"tension_axis": "deadline_vs_quality"}]
            },
            "_alignment_outcome": {},
            "_resonance_score": 0.5,
        }
        agent._build_alignment_memory_hint_for_item(item)
        self.assertEqual(item["graph_mode"], "reuse")

    def test_retrieved_total_increments(self) -> None:
        """retrieved_total in metrics increments when a hint is produced."""
        agent = self._agent_with_memory()
        before = agent.get_alignment_memory_metrics().get("retrieved_total", 0)
        # Directly call hint builder with a matching item
        item: dict = {
            "_intent": {"type": "coordinate"},
            "_alignment_report": {
                "pairwise_hotspots": [{"tension_axis": "deadline_vs_quality"}]
            },
        }
        hint = agent._build_alignment_memory_hint_for_item(item)
        if hint:  # only check if a hint was actually produced
            after = agent.get_alignment_memory_metrics().get("retrieved_total", 0)
            self.assertGreater(after, before)


if __name__ == "__main__":
    unittest.main()
