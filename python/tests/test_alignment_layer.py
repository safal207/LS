from __future__ import annotations

from graph.alignment import InteractionAlignmentAnalyzer
from modules.agent.resonance_agent import (
    ResonanceAgent,
    build_alignment_outcome_snapshot,
    build_effect_reason,
)


def test_alignment_analyzer_positive_for_shared_intent_and_why() -> None:
    analyzer = InteractionAlignmentAnalyzer()

    report = analyzer.analyze(
        [
            {
                "participant_id": "human-1",
                "participant_type": "human",
                "intent": "resolve_issue",
                "why": "restore_trust",
                "need_vector": ["clarity", "care"],
            },
            {
                "participant_id": "agent-1",
                "participant_type": "agent",
                "intent": "resolve_issue",
                "why": "restore_trust",
                "need_vector": ["clarity", "care"],
            },
        ]
    )

    assert report.alignment_score >= 0.65
    assert report.tension_score <= 0.30
    assert "shared_intent:resolve_issue" in report.agreement_reasons


def test_alignment_analyzer_raises_tension_for_conflicting_direction_and_pressure() -> None:
    analyzer = InteractionAlignmentAnalyzer()

    report = analyzer.analyze(
        [
            {
                "participant_id": "human-1",
                "intent": "ship_now",
                "why": "deadline",
                "need_vector": ["urgency", "speed"],
                "foreground_expression": ["pressure"],
                "tension_signal": 0.8,
            },
            {
                "participant_id": "agent-1",
                "intent": "verify_safety",
                "why": "risk_control",
                "need_vector": ["stability", "accuracy"],
                "background_state": ["uncertainty"],
                "tension_signal": 0.5,
            },
        ]
    )

    assert report.tension_score >= 0.45
    assert any("intent_conflict" in reason for reason in report.mismatch_reasons)
    assert report.mismatch_reasons


def test_alignment_analyzer_is_safe_with_missing_optional_fields() -> None:
    analyzer = InteractionAlignmentAnalyzer()

    report = analyzer.analyze([{"participant_id": "h1"}, {"participant_id": "a1"}])
    payload = report.to_dict()

    assert "alignment_score" in payload
    assert "tension_score" in payload
    assert isinstance(payload["participants"], list)
    assert payload["dominant_axis"] in {"alignment", "tension", "balanced"}


def test_alignment_analyzer_coerces_string_fields_without_character_splitting() -> None:
    analyzer = InteractionAlignmentAnalyzer()

    report = analyzer.analyze(
        [
            {"participant_id": "h1", "background_state": "stress", "need_vector": "clarity"},
            {"participant_id": "a1", "background_state": "stress", "need_vector": "clarity"},
        ]
    )

    first = report.participants[0]
    assert first["background_state"] == ["stress"]
    assert first["need_vector"] == ["clarity"]


def test_alignment_analyzer_multi_participant_returns_pairwise_hotspots() -> None:
    analyzer = InteractionAlignmentAnalyzer()

    report = analyzer.analyze(
        [
            {"participant_id": "human-1", "intent": "coordinate", "need_vector": ["clarity"]},
            {"participant_id": "agent-1", "intent": "coordinate", "need_vector": ["clarity"]},
            {
                "participant_id": "human-2",
                "intent": "block",
                "why": "protect_scope",
                "need_vector": ["control"],
                "tension_signal": 0.9,
            },
        ]
    )

    assert report.pairwise_hotspots
    assert any("human-2" in hotspot["participants"] for hotspot in report.pairwise_hotspots)


def test_alignment_analyzer_does_not_flag_hotspot_without_pairwise_evidence() -> None:
    analyzer = InteractionAlignmentAnalyzer()

    report = analyzer.analyze(
        [
            {"participant_id": "human-1"},
            {"participant_id": "agent-1"},
            {"participant_id": "human-2"},
        ]
    )

    assert report.pairwise_hotspots == []


def test_alignment_report_attached_to_agent_flow_without_breaking_output() -> None:
    agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")

    result = agent.process_item(
        {
            "type": "question",
            "text": "Как нам двигаться дальше по задаче?",
            "participants": [
                {
                    "participant_id": "human-1",
                    "participant_type": "human",
                    "intent": "resolve_issue",
                    "why": "keep_deadline",
                    "need_vector": ["clarity", "urgency"],
                },
                {
                    "participant_id": "agent-1",
                    "participant_type": "agent",
                    "intent": "resolve_issue",
                    "why": "keep_deadline",
                    "need_vector": ["clarity", "accuracy"],
                },
            ],
        }
    )

    assert result["final_output"]
    assert "alignment_report" in result
    assert isinstance(result["alignment_report"], dict)
    assert "alignment_score" in result["alignment_report"]
    assert "alignment_outcome" in result
    assert "alignment_observability" in result


def test_alignment_guidance_added_to_system_prompt_when_report_requires_softening() -> None:
    agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
    item = {
        "text": "Как нам договориться без конфликта?",
        "_copilot_output": {},
        "_graph_runtime": {},
        "_path_selection": {},
        "_resonance_score": 0.5,
        "_alignment_report": {
            "requires_softening": True,
            "requires_clarification": True,
            "requires_grounding": False,
            "suggested_mode": "soften",
        },
    }

    system_prompt = agent._build_system_prompt(item)

    assert "Alignment guidance" in system_prompt
    assert item.get("_alignment_guidance")


def test_alignment_observability_counts_guidance_outcomes() -> None:
    agent = ResonanceAgent(anchor=[], llm_fn=lambda _u, _s: "Понимаю, давай сначала уточним контекст.", orientation="test")
    result = agent.process_item(
        {
            "type": "question",
            "text": "Почему мы опять спорим по одному и тому же?",
            "participants": [
                {
                    "participant_id": "human-1",
                    "participant_type": "human",
                    "intent": "ship_now",
                    "why": "deadline",
                    "need_vector": ["urgency", "speed"],
                    "foreground_expression": ["pressure"],
                    "tension_signal": 0.9,
                },
                {
                    "participant_id": "agent-1",
                    "participant_type": "agent",
                    "intent": "verify_safety",
                    "why": "risk_control",
                    "need_vector": ["stability", "accuracy"],
                    "tension_signal": 0.7,
                },
            ],
        }
    )

    outcome = result["alignment_outcome"]
    metrics = result["alignment_observability"]
    assert outcome["guidance_added"] is True
    assert outcome["guidance_effective"] is True
    assert metrics["guidance_added_count"] >= 1
    assert metrics["guidance_effective_count"] >= 1


# ---------------------------------------------------------------------------
# Per-cycle effect_reason tests (1-5)
# ---------------------------------------------------------------------------

_SNAPSHOT_KEYS = frozenset(
    {
        "guidance_added",
        "pre_tension_score",
        "post_resonance_score",
        "post_goal_alignment_score",
        "response_softened",
        "softening_score",
        "softening_signals",
        "effect_reason",
        "guidance_effective",
    }
)


def test_positive_softening_cycle_has_nonempty_effect_reason() -> None:
    """Cycle with detected softening signals produces a non-empty effect_reason."""
    reason = build_effect_reason(
        signals=["bridge_phrase", "pacing_marker"],
        softening_detected=True,
        guidance_applied=False,
        guidance_effective=False,
        goal_alignment_score=0.5,
    )
    assert reason
    assert "bridge_phrase" in reason
    assert "pacing_marker" in reason


def test_neutral_cycle_has_meaningful_reason() -> None:
    """No signals, no guidance → neutral but readable reason."""
    reason = build_effect_reason(
        signals=[],
        softening_detected=False,
        guidance_applied=False,
        guidance_effective=False,
        goal_alignment_score=0.3,
    )
    assert reason
    assert reason == "no clear softening signals detected"


def test_guidance_applied_weak_effect_has_soft_reason() -> None:
    """Guidance applied but softening not detected → explains weak effect."""
    reason = build_effect_reason(
        signals=[],
        softening_detected=False,
        guidance_applied=True,
        guidance_effective=False,
        goal_alignment_score=0.4,
    )
    assert "weak" in reason or "applied" in reason


def test_effect_reason_is_deterministic() -> None:
    """Same inputs → identical reason string, every time."""
    kwargs = dict(
        signals=["acknowledgment"],
        softening_detected=True,
        guidance_applied=True,
        guidance_effective=True,
        goal_alignment_score=0.7,
    )
    assert build_effect_reason(**kwargs) == build_effect_reason(**kwargs)


def test_effect_reason_has_no_duplicate_signal_labels() -> None:
    """Signal labels appear at most once in the reason string."""
    signals = ["bridge_phrase", "bridge_phrase", "pacing_marker"]
    reason = build_effect_reason(
        signals=signals,
        softening_detected=True,
        guidance_applied=False,
        guidance_effective=False,
        goal_alignment_score=0.5,
    )
    # bridge_phrase capped to one occurrence in the label portion
    assert reason.count("bridge_phrase") == 1


# ---------------------------------------------------------------------------
# Snapshot structure tests (6-10)
# ---------------------------------------------------------------------------


def test_snapshot_contains_expected_keys() -> None:
    """build_alignment_outcome_snapshot returns all required keys."""
    snap = build_alignment_outcome_snapshot(
        guidance_applied=False,
        pre_tension_score=0.3,
        post_resonance_score=0.6,
        post_goal_alignment_score=0.55,
        softening_detected=False,
        softening_score=0.0,
        softening_signals=[],
        guidance_effective=False,
    )
    assert _SNAPSHOT_KEYS == set(snap.keys())


def test_snapshot_contains_no_extra_keys() -> None:
    """Snapshot must not silently grow with undocumented fields."""
    snap = build_alignment_outcome_snapshot(
        guidance_applied=True,
        pre_tension_score=0.5,
        post_resonance_score=0.7,
        post_goal_alignment_score=0.68,
        softening_detected=True,
        softening_score=0.5,
        softening_signals=["bridge_phrase", "acknowledgment"],
        guidance_effective=True,
    )
    assert set(snap.keys()) == _SNAPSHOT_KEYS


def test_snapshot_softening_signals_is_list() -> None:
    """softening_signals field in snapshot is always a list."""
    snap = build_alignment_outcome_snapshot(
        guidance_applied=False,
        pre_tension_score=0.0,
        post_resonance_score=0.5,
        post_goal_alignment_score=0.4,
        softening_detected=True,
        softening_score=0.25,
        softening_signals=["pacing_marker"],
        guidance_effective=False,
    )
    assert isinstance(snap["softening_signals"], list)


def test_snapshot_effect_reason_is_json_serializable() -> None:
    """effect_reason must be a plain string, safe for logs and API output."""
    import json

    snap = build_alignment_outcome_snapshot(
        guidance_applied=True,
        pre_tension_score=0.6,
        post_resonance_score=0.75,
        post_goal_alignment_score=0.7,
        softening_detected=True,
        softening_score=0.5,
        softening_signals=["bridge_phrase"],
        guidance_effective=True,
    )
    serialised = json.dumps(snap, ensure_ascii=False)
    assert snap["effect_reason"] in serialised


def test_snapshot_is_backward_compatible_with_existing_outcome_keys() -> None:
    """Keys used by existing tests / consumers must remain present."""
    snap = build_alignment_outcome_snapshot(
        guidance_applied=True,
        pre_tension_score=0.4,
        post_resonance_score=0.65,
        post_goal_alignment_score=0.6,
        softening_detected=False,
        softening_score=0.0,
        softening_signals=[],
        guidance_effective=True,
    )
    # Keys checked by existing test_alignment_observability_counts_guidance_outcomes
    assert "guidance_added" in snap
    assert "guidance_effective" in snap


# ---------------------------------------------------------------------------
# Safety / advisory-only tests (11-14)
# ---------------------------------------------------------------------------


def test_snapshot_does_not_set_graph_mode() -> None:
    """build_alignment_outcome_snapshot returns a plain dict with no graph_mode."""
    snap = build_alignment_outcome_snapshot(
        guidance_applied=False,
        pre_tension_score=0.0,
        post_resonance_score=0.5,
        post_goal_alignment_score=0.4,
        softening_detected=False,
        softening_score=0.0,
        softening_signals=[],
        guidance_effective=False,
    )
    assert "graph_mode" not in snap


def test_snapshot_does_not_set_route_key() -> None:
    """build_alignment_outcome_snapshot must never carry route_key."""
    snap = build_alignment_outcome_snapshot(
        guidance_applied=False,
        pre_tension_score=0.0,
        post_resonance_score=0.5,
        post_goal_alignment_score=0.4,
        softening_detected=False,
        softening_score=0.0,
        softening_signals=[],
        guidance_effective=False,
    )
    assert "route_key" not in snap


def test_reuse_mode_item_graph_mode_unchanged_after_outcome() -> None:
    """_record_alignment_outcome must not touch item['graph_mode']."""
    agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
    item: dict = {
        "graph_mode": "reuse",
        "_alignment_report": {},
        "_alignment_guidance": "",
        "_resonance_score": 0.5,
    }
    agent._record_alignment_outcome(item, response_text="ok", response_score=0.6, goal_alignment_score=0.5)
    assert item["graph_mode"] == "reuse"


def test_guidance_builder_behavior_unchanged_by_snapshot_refactor() -> None:
    """_build_system_prompt still injects alignment guidance when required."""
    agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="test")
    item = {
        "_alignment_report": {
            "requires_softening": True,
            "requires_clarification": False,
            "requires_grounding": False,
            "suggested_mode": "soften",
        },
        "_copilot_output": {},
        "_graph_runtime": {},
        "_path_selection": {},
        "_resonance_score": 0.5,
    }
    prompt = agent._build_system_prompt(item)
    assert "Alignment guidance" in prompt


# ---------------------------------------------------------------------------
# Observability separation tests (15-16)
# ---------------------------------------------------------------------------


def test_per_cycle_snapshot_does_not_break_aggregate_metrics() -> None:
    """After a full process_item cycle, aggregate metrics remain populated."""
    agent = ResonanceAgent(
        anchor=[],
        llm_fn=lambda _u, _s: "Понимаю, давай разберёмся вместе.",
        orientation="test",
    )
    agent.process_item({"type": "question", "text": "Тест агрегации метрик."})
    metrics = agent.get_alignment_outcome_metrics()
    assert metrics["observed_cycles"] >= 1


def test_aggregate_metrics_keep_accumulating_across_cycles() -> None:
    """Each process_item call increments observed_cycles independently of snapshot."""
    agent = ResonanceAgent(
        anchor=[],
        llm_fn=lambda _u, _s: "Хорошо, понял.",
        orientation="test",
    )
    agent.process_item({"type": "question", "text": "Первый вопрос."})
    agent.process_item({"type": "question", "text": "Второй вопрос."})
    metrics = agent.get_alignment_outcome_metrics()
    assert metrics["observed_cycles"] >= 2
