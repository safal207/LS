from __future__ import annotations

from graph.alignment import InteractionAlignmentAnalyzer
from modules.agent.resonance_agent import ResonanceAgent


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
