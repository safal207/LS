from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path = [p for p in sys.path if not p.endswith("/python/modules")] + [p for p in sys.path if p.endswith("/python/modules")]

from agent.decision_pipeline import DecisionPipeline
from agent.reflection import ReflectionPipeline
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
        "memory_graph": {
            "nodes": [{"id": "n1"}],
            "edges": [{"source": "n1", "target": "n1"}],
        },
        "recent_reflections": [
            {"id": "r1", "timestamp": "2026-03-13T12:30:00+00:00"},
            {"id": "r2", "timestamp": "2026-03-13T13:30:00+00:00"},
        ],
        "reflection_dashboard_log": [{"action": "reject", "messages": ["x"]}],
        "pipeline_activity": [
            {
                "timestamp": datetime(2026, 3, 13, 13, 15, tzinfo=timezone.utc).isoformat(),
                "type": "approve",
                "details": {},
            },
            {
                "timestamp": datetime(2026, 3, 13, 13, 45, tzinfo=timezone.utc).isoformat(),
                "type": "reject",
                "details": {},
            },
        ],
    }
    decision_pipeline = DecisionPipeline(state, tool_registry={"answer_with_tool": _dummy_tool})
    pipeline = ReflectionPipeline(decision_pipeline)
    return ReflectionDashboardService(pipeline)


def test_snapshot_contains_contract_sections() -> None:
    service = build_service()

    snapshot = service.get_dashboard_snapshot(recent_limit=1)

    assert set(snapshot.keys()) >= {"memory_graph", "recent_reflections", "metrics", "heatmap", "proposals", "updated_at"}
    assert snapshot["memory_graph"]["nodes"]
    assert len(snapshot["recent_reflections"]) == 1


def test_metrics_and_heatmap_aggregation() -> None:
    service = build_service()

    metrics = service.get_metrics(proposals=[{"confidence": 0.9}, {"confidence": 0.3}])
    heatmap = service.get_heatmap_data()

    assert metrics["confidence_score"] == 0.6
    assert metrics["contradiction_count"] == 1
    assert heatmap
    assert heatmap[0]["count"] == 2
    assert heatmap[0]["approve"] == 1
    assert heatmap[0]["reject"] == 1


def test_edit_creates_new_version_and_logs_activity() -> None:
    service = build_service()

    proposal = {
        "proposal_id": "p1",
        "change_type": "control_update",
        "target": "fallback_action",
        "proposed_value": "retrieve_context",
        "confidence": 0.91,
    }

    messages = service.edit(proposal, proposed_value="structured_reasoning")

    assert any("fallback_action=structured_reasoning" in item for item in messages)
    activity = service.pipeline.cognitive_state["pipeline_activity"]
    assert activity[-1]["type"] == "edit"
    assert activity[-1]["details"]["parent_proposal_id"] == "p1"
