"""Tests for reflection dashboard proposal application workflow."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from agent.decision_pipeline import DecisionPipeline
from agent.reflection_actions import ReflectionActionHandler


def _dummy_tool(payload: dict) -> dict:
    return {"status": "ok", "payload": payload}


def build_pipeline() -> DecisionPipeline:
    cognitive_state = {
        "action_history": [{"success": True}],
        "strategy_stats": {
            "retrieve_context": {"successes": 1, "attempts": 1, "total_value": 1.0},
            "answer_with_tool": {"successes": 1, "attempts": 1, "total_value": 1.0},
            "structured_reasoning": {"successes": 1, "attempts": 1, "total_value": 1.0},
        },
        "action_log": [{"fallback_reason": None}],
        "tool_error_counts": {"answer_with_tool": 7},
    }
    return DecisionPipeline(cognitive_state, tool_registry={"answer_with_tool": _dummy_tool})


def test_apply_control_and_tool_demotion() -> None:
    pipeline = build_pipeline()
    handler = ReflectionActionHandler(pipeline)

    proposals = [
        {
            "proposal_id": "p1",
            "change_type": "control_update",
            "target": "low_confidence_threshold",
            "proposed_value": 0.55,
        },
        {
            "proposal_id": "p2",
            "change_type": "control_update",
            "target": "fallback_action",
            "proposed_value": "structured_reasoning",
        },
        {
            "proposal_id": "p3",
            "change_type": "tool_demotion",
            "target": "answer_with_tool",
            "proposed_value": None,
        },
    ]

    messages = handler.apply_selected(proposals)

    assert pipeline.low_confidence_threshold == 0.55
    assert pipeline.fallback_action == "structured_reasoning"
    assert pipeline.tool_runtime.execute("answer_with_tool", {})["status"] == "disabled"
    assert len(messages) == 3


def test_auto_apply_high_confidence_roundtrip() -> None:
    pipeline = build_pipeline()
    handler = ReflectionActionHandler(pipeline)

    proposals = [
        {
            "proposal_id": "p-hi",
            "change_type": "control_update",
            "target": "low_confidence_threshold",
            "proposed_value": 0.9,
            "confidence": 0.95,
        },
        {
            "proposal_id": "p-low",
            "change_type": "control_update",
            "target": "fallback_action",
            "proposed_value": "structured_reasoning",
            "confidence": 0.6,
        },
    ]

    messages = handler.auto_apply_high_confidence(proposals)

    assert pipeline.low_confidence_threshold == 0.9
    assert any("control_update" in message for message in messages)


def test_strategy_mutation_generation_and_apply() -> None:
    pipeline = build_pipeline()
    handler = ReflectionActionHandler(pipeline)

    proposals = pipeline.generate_strategy_mutation_proposals()
    assert proposals
    assert all(item["change_type"] == "strategy_mutation" for item in proposals)

    chosen = proposals[0]
    handler.apply_selected([chosen])

    strategy_stats = pipeline.cognitive_state["strategy_stats"]
    assert chosen["proposed_value"] in strategy_stats


def test_sleep_phase_trigger_for_actions_and_time() -> None:
    pipeline = build_pipeline()

    pipeline.cognitive_state["actions_since_sleep"] = 100
    assert pipeline.should_trigger_sleep_phase()

    pipeline.cognitive_state["actions_since_sleep"] = 0
    pipeline.cognitive_state["last_sleep_phase_at"] = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    assert pipeline.should_trigger_sleep_phase()


def test_save_and_load_state_roundtrip(tmp_path: Path) -> None:
    pipeline = build_pipeline()
    pipeline.cognitive_state["custom_flag"] = "before"

    target = tmp_path / "state.json"
    pipeline.save_state(str(target))

    pipeline.cognitive_state["custom_flag"] = "after"
    pipeline.load_state(str(target))

    assert pipeline.cognitive_state["custom_flag"] == "before"
