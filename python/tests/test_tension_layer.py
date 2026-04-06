# ruff: noqa: E402
"""Tests for the Relational Tension Layer (TensionAnalyzer / TensionObservation).

Covers:
  - TensionObservation: frozen, to_dict / from_dict round-trip
  - TensionAnalyzer.observe: returns correct type, non-empty fields
  - surface_intent inference from foreground expression
  - unmet_need inference from background pressure
  - projection_direction: other / self / system / agent / situation
  - alignment_gap = tension - alignment, clamped to [-1, 1]
  - repair_strategy selection for key interaction patterns
  - interaction_scope: human-human vs human-agent (appeal projection)
  - empty / neutral text baseline
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

import pytest

from graph.tension import TensionAnalyzer, TensionObservation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_analyzer = TensionAnalyzer()


def _obs(
    text: str,
    participants: list[str] | None = None,
    scope: str = "human-human",
    context: dict | None = None,
) -> TensionObservation:
    return _analyzer.observe(
        text=text,
        participants=participants or ["alice", "bob"],
        interaction_scope=scope,
        context=context,
    )


# ---------------------------------------------------------------------------
# TensionObservation dataclass
# ---------------------------------------------------------------------------


def test_observation_is_frozen():
    obs = _obs("hello")
    with pytest.raises((AttributeError, TypeError)):
        obs.tension_score = 0.9  # type: ignore[misc]


def test_observation_round_trip():
    obs = _obs("Ты опять это сделал! Я так устала от этого")
    restored = TensionObservation.from_dict(obs.to_dict())
    assert restored.observation_id == obs.observation_id
    assert restored.tension_score == obs.tension_score
    assert restored.repair_strategy == obs.repair_strategy
    assert restored.surface_intent == obs.surface_intent
    assert restored.unmet_need == obs.unmet_need


def test_observation_to_dict_keys():
    obs = _obs("test")
    d = obs.to_dict()
    required = {
        "observation_id", "timestamp", "participants", "interaction_scope",
        "surface_intent", "background_pressure", "unmet_need",
        "projection_direction", "tension_score", "alignment_gap",
        "repair_strategy", "source_snapshot_id", "metadata",
    }
    assert required.issubset(d.keys())


def test_observation_source_snapshot_id_set():
    obs = _obs("test")
    assert obs.source_snapshot_id is not None


def test_observation_participants_preserved():
    obs = _obs("test", participants=["carol", "dave"])
    assert obs.participants == ["carol", "dave"]


def test_observation_timestamp_is_iso8601():
    from datetime import datetime
    obs = _obs("test")
    datetime.fromisoformat(obs.timestamp)


# ---------------------------------------------------------------------------
# surface_intent
# ---------------------------------------------------------------------------


def test_surface_intent_blame_on_attack():
    obs = _obs("ты виноват в этом, ты всегда так делаешь!")
    assert obs.surface_intent == "blame"


def test_surface_intent_demand_on_pressure():
    obs = _obs("сделай это немедленно, должен выполнить прямо сейчас")
    assert obs.surface_intent == "demand"


def test_surface_intent_request_help_on_appeal():
    obs = _obs("помоги мне, прошу тебя, пожалуйста")
    assert obs.surface_intent == "request_help"


def test_surface_intent_reconnect_on_repair():
    obs = _obs("давай вместе найдём решение, я слышу тебя")
    assert obs.surface_intent == "reconnect"


def test_surface_intent_observe_on_neutral():
    obs = _obs("сегодня хорошая погода")
    assert obs.surface_intent == "observe"


# ---------------------------------------------------------------------------
# unmet_need
# ---------------------------------------------------------------------------


def test_unmet_need_safety_on_fear():
    obs = _obs("мне страшно, я боюсь что случится что-то плохое")
    assert obs.unmet_need == "safety"


def test_unmet_need_relief_on_overload():
    obs = _obs("я перегружен, устал от всего, too much")
    assert obs.unmet_need == "relief_and_support"


def test_unmet_need_clear_timeline_on_urgency():
    obs = _obs("срочно! немедленно нужно решить это asap")
    assert obs.unmet_need == "clear_timeline"


def test_unmet_need_recognition_on_hurt():
    obs = _obs("это больно и обидно, hurt")
    assert obs.unmet_need == "recognition"


def test_unmet_need_none_on_neutral():
    obs = _obs("всё хорошо, спасибо")
    assert obs.unmet_need is None


# ---------------------------------------------------------------------------
# projection_direction
# ---------------------------------------------------------------------------


def test_projection_other_on_attack():
    obs = _obs("это твоя вина! ты виноват в этом")
    assert obs.projection_direction == "other"


def test_projection_self_on_withdrawal():
    obs = _obs("молчу, не хочу говорить, leave me alone")
    assert obs.projection_direction == "self"


def test_projection_self_on_defensiveness():
    obs = _obs("я не виноват в этом, это не я, defensive")
    assert obs.projection_direction == "self"


def test_projection_system_on_appeal_human_human():
    obs = _obs("помоги мне пожалуйста, прошу", scope="human-human")
    assert obs.projection_direction == "system"


def test_projection_agent_on_appeal_human_agent():
    obs = _obs("помоги мне пожалуйста, прошу", scope="human-agent")
    assert obs.projection_direction == "agent"


def test_projection_situation_on_neutral():
    obs = _obs("не уверен что делать дальше, сомневаюсь")
    assert obs.projection_direction == "situation"


# ---------------------------------------------------------------------------
# tension_score and alignment_gap
# ---------------------------------------------------------------------------


def test_tension_score_high_on_conflict():
    obs = _obs("ты всегда! никогда не слушаешь! прекрати это!! невозможно!")
    assert obs.tension_score > 0.3


def test_tension_score_low_on_neutral():
    obs = _obs("привет, как дела?")
    assert obs.tension_score < 0.3


def test_alignment_gap_positive_when_tension_dominates():
    obs = _obs("это твоя вина, ты опять всегда так делаешь!")
    assert obs.alignment_gap > 0.0


def test_alignment_gap_negative_or_zero_on_alignment():
    obs = _obs("я понимаю тебя, давай вместе, мы справимся, let's do this together")
    assert obs.alignment_gap <= 0.0


def test_alignment_gap_clamped_to_minus_one():
    obs = _obs(
        "я понимаю тебя, давай вместе, let's, i hear you, we can do this, "
        "i understand, together мы, нам важно, хочу понять, я слышу"
    )
    assert obs.alignment_gap >= -1.0


def test_alignment_gap_clamped_to_plus_one():
    obs = _obs(
        "никогда всегда должен опять невозможно хватит прекрати устала не могу "
        "always never must again impossible ты виноват твоя вина зачем ты!!"
    )
    assert obs.alignment_gap <= 1.0


# ---------------------------------------------------------------------------
# repair_strategy
# ---------------------------------------------------------------------------


def test_repair_de_escalate_on_high_tension():
    obs = _obs("это твоя вина! ты всегда так! никогда не слушаешь! прекрати!!")
    assert obs.repair_strategy != "observe_and_hold_space"


def test_repair_slow_down_on_fear_with_pressure():
    # fear + urgency/pressure combination
    obs = _obs("я боюсь! срочно должен сделать это немедленно!")
    assert obs.repair_strategy in {
        "slow_down_and_validate",
        "acknowledge_safety_before_content",
        "clarify_timeline_together",
        "de_escalate_and_reflect",
    }


def test_repair_reduce_load_on_overload():
    obs = _obs("я перегружен устал, too much, не хочу говорить, leave me")
    assert obs.repair_strategy == "reduce_load_offer_options"


def test_repair_co_create_on_alignment_appeal():
    obs = _obs("я понимаю тебя, давай вместе, помоги мне пожалуйста")
    assert obs.repair_strategy in {
        "co_create_solution",
        "respond_to_need_directly",
        "affirm_and_build",
        "deepen_connection",
    }


def test_repair_observe_on_completely_neutral():
    obs = _obs("завтра будет солнечно")
    assert obs.repair_strategy == "observe_and_hold_space"


# ---------------------------------------------------------------------------
# scope variants
# ---------------------------------------------------------------------------


def test_scope_human_agent_stored_in_observation():
    obs = _obs("помоги мне разобраться с этим кодом", scope="human-agent")
    assert obs.interaction_scope == "human-agent"


def test_scope_agent_agent_stored_in_observation():
    obs = _obs("process this task immediately", scope="agent-agent")
    assert obs.interaction_scope == "agent-agent"


# ---------------------------------------------------------------------------
# metadata
# ---------------------------------------------------------------------------


def test_metadata_contains_alignment_score():
    obs = _obs("я понимаю, давай вместе")
    assert "alignment_score" in obs.metadata
    assert isinstance(obs.metadata["alignment_score"], float)


def test_metadata_contains_dominant_signal():
    obs = _obs("test")
    assert "dominant_signal" in obs.metadata


def test_context_passed_through_to_metadata():
    obs = _obs("test", context={"session": "abc123"})
    assert obs.metadata.get("context", {}).get("session") == "abc123"
