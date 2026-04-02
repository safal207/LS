# ruff: noqa: E402
from __future__ import annotations

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULES_ROOT = ROOT / "python" / "modules"
if str(MODULES_ROOT) in sys.path:
    sys.path.remove(str(MODULES_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.decision_pipeline import DecisionPipeline
from agent.reflection import ReflectionPipeline
from agent.reflection_dashboard_api import build_snapshot_response, execute_action
from agent.reflection_dashboard_service import ReflectionDashboardService


def _dummy_tool(payload: dict) -> dict:
    return {"status": "ok", "payload": payload}


def build_service() -> ReflectionDashboardService:
    state = {
        "action_history": [{"success": True}],
        "strategy_stats": {
            "retrieve_context": {"successes": 1, "attempts": 1, "total_value": 1.0},
            "answer_with_tool": {"successes": 1, "attempts": 1, "total_value": 1.0},
        },
        "action_log": [{"fallback_reason": None}],
        "tool_error_counts": {"answer_with_tool": 7},
        "recent_reflections": [{"id": "r1", "timestamp": "2026-03-13T12:30:00+00:00"}],
        "pipeline_activity": [],
    }
    decision_pipeline = DecisionPipeline(state, tool_registry={"answer_with_tool": _dummy_tool})
    pipeline = ReflectionPipeline(decision_pipeline)
    return ReflectionDashboardService(pipeline)


def test_build_snapshot_response_honors_limits() -> None:
    service = build_service()

    snapshot = build_snapshot_response(service, {"recent_limit": ["1"], "timeline_limit": ["0"]})

    assert len(snapshot["recent_reflections"]) == 1
    assert snapshot["action_timeline"] == []


def test_execute_action_approve_and_reject() -> None:
    service = build_service()
    proposal = {
        "proposal_id": "p1",
        "change_type": "control_update",
        "target": "low_confidence_threshold",
        "proposed_value": 0.5,
    }

    approved = execute_action(service, {"action": "approve", "proposal": proposal})
    rejected = execute_action(service, {"action": "reject", "proposal": proposal, "reason": "manual_review"})

    assert approved["status"] == "ok"
    assert rejected["status"] == "ok"
    assert service.pipeline.cognitive_state["canonical_reflections"][-1]["proposal_id"] == "p1"
    assert service.pipeline.cognitive_state["reflection_contradictions"][-1]["reason"] == "manual_review"


def test_execute_action_edit_requires_proposed_value() -> None:
    service = build_service()
    proposal = {
        "proposal_id": "p2",
        "change_type": "control_update",
        "target": "fallback_action",
        "proposed_value": "retrieve_context",
    }

    with pytest.raises(ValueError, match="proposed_value"):
        execute_action(service, {"action": "edit", "proposal": proposal})
