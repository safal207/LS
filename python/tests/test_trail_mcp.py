# ruff: noqa: E402
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from ls.agent_shell.mcp_resources import MCPResourceRegistry
from ls.agent_shell.mcp_server import LSMCPServer
from ls.agent_shell.mcp_tools import MCPToolRegistry, MCPValidationError
from ls.agent_shell.testing.runtime_fixture import FixtureRuntime
from ls.agent_shell.trail_network import TrailNetworkBridge


def _runtime(tmp_path: Path) -> FixtureRuntime:
    return FixtureRuntime(state_path=tmp_path / "state.json", artifact_root=tmp_path / "artifacts")


def _bridge(tmp_path: Path) -> TrailNetworkBridge:
    return TrailNetworkBridge(
        route_store_path=tmp_path / "routes.json",
        event_log_path=tmp_path / "trail_events.jsonl",
    )


def test_trail_mcp_recommends_and_updates_route_memory(tmp_path: Path) -> None:
    tools = MCPToolRegistry(task_manager=_runtime(tmp_path), trail_network=_bridge(tmp_path))

    recommendation = tools.call_tool(
        "ls_trail_recommend_route",
        {
            "task_type": "pr_review",
            "available_backends": ["local", "gonka", "mimo"],
            "strategy_bias": "cooperative_reasoning",
        },
    )
    assert recommendation["status"] == "recommended"
    assert recommendation["route"]["route_key"] == "pr_review>local>gonka>mimo"
    assert recommendation["network_learning"] == "read_existing_route_memory_only"

    outcome = tools.call_tool(
        "ls_trail_record_outcome",
        {
            "route_key": recommendation["route"]["route_key"],
            "task_id": "pr-1",
            "task_text": "review this diff",
            "evidence_coverage": 0.9,
            "false_positive_rate": 0.05,
            "human_accepted": True,
            "ci_passed": True,
            "useful_findings": 3,
            "unsupported_claims": 0,
            "latency_ms": 1200,
        },
    )
    assert outcome["status"] == "route_memory_updated"
    assert outcome["reward"] > 0
    assert outcome["route_stats"]["runs"] == 1
    assert outcome["route_stats"]["repeatability_score"] > 0

    best = tools.call_tool("ls_trail_query_best_trails", {"route_prefix": "pr_review", "limit": 1})
    assert best["routes"][0]["route_key"] == "pr_review>local>gonka>mimo"


def test_trail_mcp_records_contribution_and_exposes_events_resource(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    runtime = _runtime(tmp_path)
    tools = MCPToolRegistry(task_manager=runtime, trail_network=bridge)
    resources = MCPResourceRegistry(runtime, trail_network=bridge)

    contribution = tools.call_tool(
        "ls_trail_submit_contribution",
        {
            "task_id": "pr-2",
            "route_key": "pr_review>draft_reviewer>risk_critic",
            "actor": "gonka",
            "role": "risk_critic",
            "evidence_refs": ["diff:src/app.py:12"],
            "note": "Flagged missing regression test.",
        },
    )
    assert contribution["accepted"] is True
    assert contribution["does_not_update_route_score"] is True

    events = resources.read_resource("trail/events", {"limit": 5})
    assert events["resource"] == "trail/events"
    assert events["events"][-1]["event_type"] == "contribution_submitted"
    assert events["events"][-1]["actor"] == "gonka"


def test_trail_mcp_validates_evidence_before_learning(tmp_path: Path) -> None:
    tools = MCPToolRegistry(task_manager=_runtime(tmp_path), trail_network=_bridge(tmp_path))

    payload = tools.call_tool(
        "ls_trail_validate_evidence",
        {
            "min_coverage": 0.75,
            "claims": [
                {"claim": "Missing tests", "evidence_refs": ["diff:tests/test_x.py"]},
                {"claim": "Unsafe shell command", "evidence_refs": []},
            ],
        },
    )
    assert payload["decision"] == "needs_evidence"
    assert payload["evidence_coverage"] == 0.5
    assert payload["unsupported_claims"] == 1


def test_trail_mcp_rejects_outcome_without_evidence_signal(tmp_path: Path) -> None:
    tools = MCPToolRegistry(task_manager=_runtime(tmp_path), trail_network=_bridge(tmp_path))

    try:
        tools.call_tool("ls_trail_record_outcome", {"route_key": "pr_review>local"})
    except MCPValidationError as exc:
        assert "at least one outcome signal is required" in str(exc)
    else:
        raise AssertionError("empty outcome must not update route memory")


def test_trail_mcp_server_lists_trail_tools_and_resources(tmp_path: Path) -> None:
    server = LSMCPServer(
        tool_registry=MCPToolRegistry(task_manager=_runtime(tmp_path), trail_network=_bridge(tmp_path))
    )

    tools = {item["name"] for item in server.handle({"action": "tools/list"})["tools"]}
    resources = {item["uri"] for item in server.handle({"action": "resources/list"})["resources"]}

    assert "ls_trail_recommend_route" in tools
    assert "ls_trail_record_outcome" in tools
    assert "trail/routes" in resources
    assert "trail/events" in resources
