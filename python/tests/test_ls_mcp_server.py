# ruff: noqa: E402
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from ls.agent_shell.mcp_resources import MCPResourceRegistry
from ls.agent_shell.mcp_server import LSMCPServer
from ls.agent_shell.mcp_tools import MCPToolRegistry, MCPValidationError
from ls.agent_shell.core.runtime import CoreTaskRuntime
from ls.agent_shell.runtime.factory import resolve_task_runtime
from ls.agent_shell.testing.runtime_fixture import FixtureRuntime


def _new_runtime(tmp_path: Path) -> FixtureRuntime:
    return FixtureRuntime(state_path=tmp_path / "state.json", artifact_root=tmp_path / "artifacts")


def _new_server(tmp_path: Path) -> LSMCPServer:
    runtime = _new_runtime(tmp_path)
    return LSMCPServer(tool_registry=MCPToolRegistry(task_manager=runtime))




def test_default_shell_binding_resolves_core_runtime(monkeypatch):
    monkeypatch.delenv("LS_TASK_RUNTIME_FACTORY", raising=False)
    runtime = resolve_task_runtime()
    assert isinstance(runtime, CoreTaskRuntime)

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


def test_run_task_waits_approval_then_approve_creates_artifact(tmp_path):
    server = _new_server(tmp_path)
    run = server.handle(
        {
            "action": "tools/call",
            "name": "ls_run_task",
            "arguments": {"prompt": "Подготовь investor opening slide для LS", "mode": "full-agent"},
        }
    )["result"]
    approved = server.handle(
        {
            "action": "tools/call",
            "name": "ls_approve",
            "arguments": {"task_id": run["task_id"], "step_id": run["current_step_id"]},
        }
    )["result"]
    artifacts = server.handle(
        {
            "action": "tools/call",
            "name": "ls_list_artifacts",
            "arguments": {"task_id": run["task_id"]},
        }
    )["result"]
    assert approved["status"] == "approved"
    assert len(artifacts["artifacts"]) == 1


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
            "arguments": {"task_id": run["task_id"], "step_id": run["current_step_id"], "reason": "Сначала покажи diff"},
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
    runtime = _new_runtime(tmp_path)
    tools = MCPToolRegistry(task_manager=runtime)
    resources = MCPResourceRegistry(runtime)
    run = tools.call_tool("ls_run_task", {"prompt": "Prepare report", "mode": "safe-write"})
    tools.call_tool("ls_approve", {"task_id": run["task_id"], "step_id": run["current_step_id"]})
    trace = resources.read_resource(f"task://{run['task_id']}/trace")
    artifacts = resources.read_resource(f"task://{run['task_id']}/artifacts")
    assert trace["events"]
    assert len(artifacts["artifacts"]) == 1


def test_persistence_across_restart(tmp_path):
    first = _new_runtime(tmp_path)
    run = first.run_task(prompt="persist me", mode="safe-write")
    second = _new_runtime(tmp_path)
    status = second.get_status(task_id=run["task_id"])
    assert status["status"] == "waiting_approval"


def test_stdio_transport_roundtrip(tmp_path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PYTHON_ROOT)
    env["LS_TASK_RUNTIME_FACTORY"] = "ls.agent_shell.testing.runtime_fixture:build_fixture_runtime"
    process = subprocess.run(
        [sys.executable, "-m", "ls.agent_shell.mcp_server"],
        input=json.dumps({"action": "tools/list"}) + "\n",
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
        check=True,
    )
    payload = json.loads([line for line in process.stdout.splitlines() if line.strip()][0])
    assert payload["ok"] is True


def test_unknown_mode_rejected(tmp_path):
    server = _new_server(tmp_path)
    with pytest.raises(MCPValidationError):
        server.handle(
            {
                "action": "tools/call",
                "name": "ls_run_task",
                "arguments": {"prompt": "x", "mode": "blocked"},
            }
        )


def test_http_transport_roundtrip(tmp_path):
    import threading
    from http.server import ThreadingHTTPServer
    from urllib.request import Request, urlopen

    from ls.agent_shell.mcp_http import MCPHTTPHandler

    server = ThreadingHTTPServer(("127.0.0.1", 0), MCPHTTPHandler)
    server.mcp = _new_server(tmp_path)  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        req = Request(
            f"http://127.0.0.1:{server.server_port}/tools/list",
            method="POST",
            data=b"{}",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        assert payload["ok"] is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
