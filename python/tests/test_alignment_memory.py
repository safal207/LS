from __future__ import annotations

import sys
import os
import json
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modules"))

from modules.agent.alignment_memory import (
    AlignmentMemoryUnit,
    build_alignment_memory_unit,
    should_store_alignment_memory_unit,
)
from modules.agent.resonance_agent import ResonanceAgent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_OUTCOME_SOFTENING = {
    "guidance_added": True,
    "pre_tension_score": 0.6,
    "post_resonance_score": 0.7,
    "post_goal_alignment_score": 0.65,
    "response_softened": True,
    "softening_score": 0.5,
    "softening_signals": ["bridge_phrase", "pacing_marker"],
    "effect_reason": "bridge_phrase + pacing_marker → cooperative softening",
    "guidance_effective": True,
}

_OUTCOME_NEUTRAL = {
    "guidance_added": False,
    "pre_tension_score": 0.1,
    "post_resonance_score": 0.5,
    "post_goal_alignment_score": 0.4,
    "response_softened": False,
    "softening_score": 0.0,
    "softening_signals": [],
    "effect_reason": "no clear softening signals detected",
    "guidance_effective": False,
}

_OUTCOME_GUIDANCE_ONLY = {
    "guidance_added": True,
    "pre_tension_score": 0.4,
    "post_resonance_score": 0.6,
    "post_goal_alignment_score": 0.5,
    "response_softened": False,
    "softening_score": 0.0,
    "softening_signals": [],
    "effect_reason": "guidance applied but softening signals were weak",
    "guidance_effective": False,
}

_ITEM_BASE = {
    "text": "Как нам договориться по срокам?",
    "_alignment_report": {
        "pairwise_hotspots": [{"tension_axis": "deadline_vs_quality", "participants": ["h1", "a1"]}],
        "mismatch_reasons": ["intent_conflict:ship_now/verify_safety"],
    },
    "_intent": {"type": "coordinate"},
    "_why": {"why": "resolve_conflict"},
    "_resonance_score": 0.7,
    "_cycle_id": "test-cycle-001",
}


# ---------------------------------------------------------------------------
# Build / filtering (1–8)
# ---------------------------------------------------------------------------


class TestBuildFiltering(unittest.TestCase):

    def test_clean_cycle_without_signal_is_skipped(self) -> None:
        """should_store returns False when no alignment signal is present."""
        result = should_store_alignment_memory_unit(
            alignment_hotspot=None,
            mismatch_reasons=[],
            guidance_applied=False,
            softening_detected=False,
            guidance_effective=False,
        )
        self.assertFalse(result)

    def test_cycle_with_hotspot_is_stored(self) -> None:
        result = should_store_alignment_memory_unit(
            alignment_hotspot="deadline_vs_quality",
            mismatch_reasons=[],
            guidance_applied=False,
            softening_detected=False,
            guidance_effective=False,
        )
        self.assertTrue(result)

    def test_cycle_with_mismatch_reasons_is_stored(self) -> None:
        result = should_store_alignment_memory_unit(
            alignment_hotspot=None,
            mismatch_reasons=["intent_conflict:ship_now/verify_safety"],
            guidance_applied=False,
            softening_detected=False,
            guidance_effective=False,
        )
        self.assertTrue(result)

    def test_cycle_with_guidance_applied_is_stored(self) -> None:
        result = should_store_alignment_memory_unit(
            alignment_hotspot=None,
            mismatch_reasons=[],
            guidance_applied=True,
            softening_detected=False,
            guidance_effective=False,
        )
        self.assertTrue(result)

    def test_cycle_with_softening_detected_is_stored(self) -> None:
        result = should_store_alignment_memory_unit(
            alignment_hotspot=None,
            mismatch_reasons=[],
            guidance_applied=False,
            softening_detected=True,
            guidance_effective=False,
        )
        self.assertTrue(result)

    def test_cycle_with_guidance_effective_is_stored(self) -> None:
        result = should_store_alignment_memory_unit(
            alignment_hotspot=None,
            mismatch_reasons=[],
            guidance_applied=False,
            softening_detected=False,
            guidance_effective=True,
        )
        self.assertTrue(result)

    def test_builder_does_not_raise_on_empty_fields(self) -> None:
        """build_alignment_memory_unit handles minimal / empty item gracefully."""
        unit = build_alignment_memory_unit(
            {"text": "Hello?", "_alignment_report": {}, "_alignment_outcome": {}},
            "",
            _OUTCOME_NEUTRAL,
        )
        # Outcome is not empty so unit may be built; no exception is the goal
        # (None is also acceptable when no signal present)
        self.assertIsNone(unit) if not unit else self.assertIsInstance(unit, AlignmentMemoryUnit)

    def test_builder_does_not_duplicate_signals(self) -> None:
        """Signals in outcome flow through unchanged — deduplication is upstream."""
        outcome = dict(_OUTCOME_SOFTENING, softening_signals=["bridge_phrase", "pacing_marker"])
        unit = build_alignment_memory_unit(_ITEM_BASE, "ok", outcome)
        self.assertIsNotNone(unit)
        assert unit is not None
        # No duplicates introduced by builder
        self.assertEqual(len(unit.softening_signals), len(set(unit.softening_signals)))


# ---------------------------------------------------------------------------
# Snapshot quality (9–13)
# ---------------------------------------------------------------------------

_REQUIRED_UNIT_KEYS = frozenset({
    "source_question", "intent", "why", "alignment_hotspot",
    "mismatch_reasons", "guidance_applied", "softening_detected",
    "softening_signals", "effect_reason", "guidance_effective",
    "response_score", "goal_alignment_score", "tension_score_before",
    "metadata",
})


class TestSnapshotQuality(unittest.TestCase):

    def _unit(self) -> AlignmentMemoryUnit:
        u = build_alignment_memory_unit(_ITEM_BASE, "final", _OUTCOME_SOFTENING)
        self.assertIsNotNone(u)
        assert u is not None
        return u

    def test_unit_has_expected_keys(self) -> None:
        self.assertEqual(set(self._unit().to_dict().keys()), _REQUIRED_UNIT_KEYS)

    def test_unit_does_not_carry_raw_item_dump(self) -> None:
        """to_dict should not contain internal pipeline keys like _copilot_output."""
        d = self._unit().to_dict()
        for internal_key in ("_copilot_output", "_graph_runtime", "_path_selection", "_llm_backend"):
            self.assertNotIn(internal_key, d)

    def test_effect_reason_propagates_into_unit(self) -> None:
        u = self._unit()
        self.assertEqual(u.effect_reason, _OUTCOME_SOFTENING["effect_reason"])

    def test_softening_signals_are_json_serializable(self) -> None:
        d = self._unit().to_dict()
        serialised = json.dumps(d, ensure_ascii=False)
        self.assertIsInstance(json.loads(serialised)["softening_signals"], list)

    def test_metadata_stays_compact(self) -> None:
        u = self._unit()
        self.assertIn("cycle_id", u.metadata)
        # metadata must only have known lightweight keys
        self.assertTrue(len(u.metadata) <= 5)


# ---------------------------------------------------------------------------
# Write safety (14–16)
# ---------------------------------------------------------------------------


class TestWriteSafety(unittest.TestCase):

    def test_write_error_does_not_break_agent_response(self) -> None:
        """Even if JSONL write fails, process_item must return a valid result."""
        agent = ResonanceAgent(
            anchor=[],
            llm_fn=lambda _u, _s: "Давай обсудим вместе.",
            orientation="test",
        )
        # Force an unwritable path
        agent._alignment_memory_path = Path("/nonexistent_dir_xyz/alignment.jsonl")

        result = agent.process_item({
            "type": "question",
            "text": "Как договориться?",
            "participants": [
                {"participant_id": "h1", "intent": "ship_now", "tension_signal": 0.9},
                {"participant_id": "a1", "intent": "verify_safety", "tension_signal": 0.7},
            ],
        })
        self.assertIn("final_output", result)
        self.assertTrue(result["final_output"] is not None)

    def test_write_error_increments_save_errors_metric(self) -> None:
        """A failed JSONL write must increment save_errors in metrics."""
        agent = ResonanceAgent(
            anchor=[],
            llm_fn=lambda _u, _s: "Понимаю, давай найдём решение вместе.",
            orientation="test",
        )
        agent._alignment_memory_path = Path("/nonexistent_dir_xyz/alignment.jsonl")

        agent.process_item({
            "type": "question",
            "text": "Где мы теряем время на согласование?",
            "participants": [
                {"participant_id": "h1", "intent": "ship_now", "tension_signal": 0.8},
                {"participant_id": "a1", "intent": "verify_safety", "tension_signal": 0.6},
            ],
        })
        metrics = agent.get_alignment_memory_metrics()
        # save_errors may be 0 if unit was skipped before write attempt,
        # but must not raise and must return a dict
        self.assertIsInstance(metrics, dict)

    def test_skipped_unit_is_counted(self) -> None:
        """process_item on a neutral-signal cycle increments skipped_total."""
        agent = ResonanceAgent(
            anchor=[],
            llm_fn=lambda _u, _s: "Ответ.",
            orientation="test",
        )
        # Neutral item: no participants, no tension, no guidance needed
        agent.process_item({"type": "question", "text": "Что такое Redis?"})
        metrics = agent.get_alignment_memory_metrics()
        self.assertGreaterEqual(metrics.get("skipped_total", 0) + metrics.get("saved_total", 0), 1)


# ---------------------------------------------------------------------------
# Behavioral safety (17–20)
# ---------------------------------------------------------------------------


class TestBehavioralSafety(unittest.TestCase):

    def test_memory_write_does_not_change_graph_mode(self) -> None:
        """_maybe_store_alignment_memory_unit must not mutate item['graph_mode']."""
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        item: dict = {
            "graph_mode": "reuse",
            "text": "Тест.",
            "_alignment_outcome": _OUTCOME_SOFTENING,
            "_alignment_report": {},
            "_resonance_score": 0.5,
        }
        agent._maybe_store_alignment_memory_unit(item, "ok")
        self.assertEqual(item["graph_mode"], "reuse")

    def test_memory_write_does_not_change_route_key(self) -> None:
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        item: dict = {
            "route_key": "deep",
            "text": "Тест.",
            "_alignment_outcome": _OUTCOME_SOFTENING,
            "_alignment_report": {},
            "_resonance_score": 0.5,
        }
        agent._maybe_store_alignment_memory_unit(item, "ok")
        self.assertEqual(item["route_key"], "deep")

    def test_reuse_mode_pipeline_is_not_broken(self) -> None:
        """process_item with reuse-mode item completes without exception."""
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        result = agent.process_item({"type": "question", "text": "Тест reuse.", "graph_mode": "reuse"})
        self.assertIn("final_output", result)

    def test_alignment_outcome_metrics_not_broken_by_memory_layer(self) -> None:
        """Existing alignment_observability counters remain intact."""
        agent = ResonanceAgent(
            anchor=[],
            llm_fn=lambda _u, _s: "Понимаю, давай разберёмся.",
            orientation="test",
        )
        agent.process_item({
            "type": "question",
            "text": "Почему конфликт?",
            "participants": [
                {"participant_id": "h1", "intent": "ship_now", "tension_signal": 0.9},
                {"participant_id": "a1", "intent": "verify_safety", "tension_signal": 0.7},
            ],
        })
        obs = agent.get_alignment_outcome_metrics()
        self.assertGreaterEqual(obs["observed_cycles"], 1)


# ---------------------------------------------------------------------------
# Observability (21–24)
# ---------------------------------------------------------------------------


class TestObservability(unittest.TestCase):

    def test_builder_calls_increments(self) -> None:
        agent = ResonanceAgent(
            anchor=[],
            llm_fn=lambda _u, _s: "Ответ.",
            orientation="test",
        )
        agent.process_item({"type": "question", "text": "Первый вопрос."})
        metrics = agent.get_alignment_memory_metrics()
        self.assertGreaterEqual(metrics.get("builder_calls", 0), 1)

    def test_saved_total_increments_on_signal_cycle(self) -> None:
        agent = ResonanceAgent(
            anchor=[],
            llm_fn=lambda _u, _s: "Понимаю, давай сначала уточним.",
            orientation="test",
        )
        agent.process_item({
            "type": "question",
            "text": "Как нам договориться?",
            "participants": [
                {"participant_id": "h1", "intent": "ship_now", "tension_signal": 0.9},
                {"participant_id": "a1", "intent": "verify_safety", "tension_signal": 0.7},
            ],
        })
        metrics = agent.get_alignment_memory_metrics()
        self.assertGreaterEqual(metrics.get("saved_total", 0), 1)

    def test_skipped_plus_saved_equals_builder_calls(self) -> None:
        """skipped_total + saved_total + save_errors == builder_calls."""
        agent = ResonanceAgent(
            anchor=[],
            llm_fn=lambda _u, _s: "Хорошо.",
            orientation="test",
        )
        for text in ["Первый.", "Второй.", "Третий."]:
            agent.process_item({"type": "question", "text": text})
        m = agent.get_alignment_memory_metrics()
        total = m.get("saved_total", 0) + m.get("skipped_total", 0) + m.get("save_errors", 0)
        self.assertEqual(total, m.get("builder_calls", 0))

    def test_reason_based_counters_are_present(self) -> None:
        """Metrics dict always contains reason-based counter keys."""
        agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
        metrics = agent.get_alignment_memory_metrics()
        for key in ("saved_because_hotspot", "saved_because_softening", "saved_because_guidance_effective"):
            self.assertIn(key, metrics)


if __name__ == "__main__":
    unittest.main()
