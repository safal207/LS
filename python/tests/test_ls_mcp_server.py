# ruff: noqa: E402
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from python.ls.agent_shell.mcp_resources import MCPResourceRegistry
from python.ls.agent_shell.mcp_server import LSMCPServer
from python.ls.agent_shell.mcp_tools import MCPToolRegistry, MCPValidationError, TaskManager


def _new_server(tmp_path: Path) -> LSMCPServer:
    task_manager = TaskManager(artifact_root=tmp_path / "artifacts")
    return LSMCPServer(tool_registry=MCPToolRegistry(task_manager=task_manager))


def test_plan_task_generates_blocked_plan(tmp_path):
    server = _new_server(tmp_path)

    response = server.handle(
        {
            "action": "tools/call",
            "name": "ls_plan_task",
            "arguments": {"prompt": "Проверь PR #387 и дай review", "mode": "safe-write"},
        }
    )

    result = response["result"]
    assert result["task_id"].startswith("task-")
    assert result["status"] == "blocked"
    assert result["plan"][0]["type"] == "read"
    assert result["summary"] == "Plan generated only."


def test_run_task_waits_approval_then_approve_creates_artifact(tmp_path):
    server = _new_server(tmp_path)

    run = server.handle(
        {
            "action": "tools/call",
            "name": "ls_run_task",
            "arguments": {"prompt": "Подготовь investor opening slide для LS", "mode": "safe-write"},
        }
    )["result"]

    assert run["status"] == "waiting_approval"
    task_id = run["task_id"]
    step_id = run["current_step_id"]

    status = server.handle(
        {
            "action": "tools/call",
            "name": "ls_get_status",
            "arguments": {"task_id": task_id},
        }
    )["result"]
    assert status["status"] == "waiting_approval"

    approved = server.handle(
        {
            "action": "tools/call",
            "name": "ls_approve",
            "arguments": {"task_id": task_id, "step_id": step_id},
        }
    )["result"]
    assert approved["status"] == "approved"

    artifacts = server.handle(
        {
            "action": "tools/call",
            "name": "ls_list_artifacts",
            "arguments": {"task_id": task_id},
        }
    )["result"]
    assert len(artifacts["artifacts"]) == 1
    assert artifacts["artifacts"][0]["path_or_url"].endswith("report.md")


def test_reject_blocks_task_and_prevents_resume(tmp_path):
    server = _new_server(tmp_path)

    run = server.handle(
        {
            "action": "tools/call",
            "name": "ls_run_task",
            "arguments": {"prompt": "Do write", "mode": "safe-write"},
        }
    )["result"]

    server.handle(
        {
            "action": "tools/call",
            "name": "ls_reject",
            "arguments": {
                "task_id": run["task_id"],
                "step_id": run["current_step_id"],
                "reason": "Сначала покажи diff",
            },
        }
    )

    with pytest.raises(MCPValidationError):
        server.handle(
            {
                "action": "tools/call",
                "name": "ls_resume_task",
                "arguments": {"task_id": run["task_id"]},
            }
        )


def test_trace_and_artifact_resources(tmp_path):
    manager = TaskManager(artifact_root=tmp_path / "artifacts")
    tools = MCPToolRegistry(task_manager=manager)
    resources = MCPResourceRegistry(manager)

    run = tools.call_tool("ls_run_task", {"prompt": "Prepare report", "mode": "safe-write"})
    task_id = run["task_id"]
    step_id = run["current_step_id"]
    tools.call_tool("ls_approve", {"task_id": task_id, "step_id": step_id})

    trace = resources.read_resource(f"task://{task_id}/trace")
    assert trace["events"]
    assert "approvals" in trace

    artifacts = resources.read_resource(f"task://{task_id}/artifacts")
    assert len(artifacts["artifacts"]) == 1


def test_unknown_mode_rejected(tmp_path):
    server = _new_server(tmp_path)
    with pytest.raises(MCPValidationError):
        server.handle(
            {
                "action": "tools/call",
                "name": "ls_run_task",
                "arguments": {"prompt": "x", "mode": "danger-mode"},
            }
        )
