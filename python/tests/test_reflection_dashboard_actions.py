"""Tests for reflection dashboard proposal application workflow."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.decision_pipeline import DecisionPipeline
from agent.reflection_actions import ReflectionActionHandler


def _dummy_tool(payload: dict) -> dict:
    return {"status": "ok", "payload": payload}


def build_pipeline() -> DecisionPipeline:
    cognitive_state = {
        "action_history": [{"success": True}],
        "strategy_stats": {"retrieve_context": {"successes": 1, "attempts": 1, "total_value": 1.0}},
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


def test_save_and_load_state_roundtrip(tmp_path: Path) -> None:
    pipeline = build_pipeline()
    pipeline.cognitive_state["custom_flag"] = "before"

    target = tmp_path / "state.json"
    pipeline.save_state(str(target))

    pipeline.cognitive_state["custom_flag"] = "after"
    pipeline.load_state(str(target))

    assert pipeline.cognitive_state["custom_flag"] == "before"
