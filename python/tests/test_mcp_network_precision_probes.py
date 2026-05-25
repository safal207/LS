# ruff: noqa: E402
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"

from ls.agent_shell.mcp_server import LSMCPServer
from ls.agent_shell.mcp_tools import MCPToolRegistry
from ls.agent_shell.testing.runtime_fixture import FixtureRuntime


def _runtime(tmp_path: Path) -> FixtureRuntime:
    return FixtureRuntime(state_path=tmp_path / "state.json", artifact_root=tmp_path / "artifacts")


def test_mcp_network_precision_tools_are_registered(tmp_path: Path) -> None:
    tools = MCPToolRegistry(task_manager=_runtime(tmp_path))
    names = {item["name"] for item in tools.list_tools()}

    assert "ls_run_network_precision_probe" in names
    assert "ls_run_model_roster_probe" in names
    assert "ls_run_network_trajectory_probe" in names
    assert "ls_run_live_model_pilot" in names
    assert "ls_prepare_contributor_report" in names


def test_mcp_server_lists_network_precision_tools(tmp_path: Path) -> None:
    server = LSMCPServer(tool_registry=MCPToolRegistry(task_manager=_runtime(tmp_path)))
    tools = {item["name"] for item in server.handle({"action": "tools/list"})["tools"]}

    assert "ls_run_network_precision_probe" in tools
    assert "ls_run_model_roster_probe" in tools
    assert "ls_run_network_trajectory_probe" in tools
    assert "ls_run_live_model_pilot" in tools
    assert "ls_prepare_contributor_report" in tools


def _mcp_call(name: str, arguments: dict[str, object]) -> dict[str, object]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PYTHON_ROOT)
    env["LS_TASK_RUNTIME_FACTORY"] = "ls.agent_shell.testing.runtime_fixture:build_fixture_runtime"

    request = json.dumps({"action": "tools/call", "name": name, "arguments": arguments}) + "\n"
    process = subprocess.run(
        [sys.executable, "-m", "ls.agent_shell.mcp_server"],
        input=request.encode("utf-8"),
        capture_output=True,
        text=False,
        cwd=str(ROOT),
        env=env,
        check=True,
    )
    stdout = process.stdout.decode("utf-8", errors="replace") if process.stdout else ""
    payload = json.loads([line for line in stdout.splitlines() if line.strip()][0])
    return payload["result"]


def test_mcp_network_precision_probe_subprocess() -> None:
    result = _mcp_call("ls_run_network_precision_probe", {})

    assert result["tool"] == "ls_run_network_precision_probe"
    assert result["metric_version"] == "network_precision_gain.v0.2"
    assert result["measured_route_reward_gain"] > 0
    assert result["network_precision"]["network_precision_gain_over_baseline"] > 0
    assert len(result["variants"]) == 3
    assert "temporal_observer_detail" in result
    assert "scope_bridge_detail" in result


def test_mcp_model_roster_probe_subprocess() -> None:
    result = _mcp_call("ls_run_model_roster_probe", {})

    assert result["tool"] == "ls_run_model_roster_probe"
    assert result["metric_version"] == "model_roster_depth_probe.v0.1"
    assert "codex-self-use" in {item["actor_id"] for item in result["roster"]}
    assert "available_now" in result["interpretation"]


def test_mcp_prepare_contributor_report_subprocess() -> None:
    result = _mcp_call("ls_prepare_contributor_report", {"runner": "mcp-test"})

    assert result["tool"] == "ls_prepare_contributor_report"
    assert result["report_version"] == "network_precision_contributor_report.v0.1"
    assert result["runner"] == "mcp-test"
    assert result["summary"]["network_precision_gain_over_baseline"] > 0
    assert "codex-self-use" in result["summary"]["ready_actors"]
    assert "os" in result["environment"]
    assert "python_version" in result["environment"]
    assert "boundary" in result


def test_mcp_network_trajectory_probe_subprocess() -> None:
    result = _mcp_call("ls_run_network_trajectory_probe", {"cycles": 4})

    assert result["tool"] == "ls_run_network_trajectory_probe"
    assert result["metric_version"] == "network_trajectory.v0.2"
    assert result["source_metric_version"] == "network_precision_gain.v0.2"
    assert result["cycles"] == 4
    assert result["conductor_policy"]["version"] == "conductor.v0.2"
    assert result["conductor_policy"]["uses_reason_freshness"] is True
    assert result["summary"]["observer_delta_final"] > 0
    assert result["summary"]["observer_velocity_multiplier"] > 0
    assert result["summary"]["conductor_observer_delta"] > 0
    assert len(result["trajectory"]) == 4
    assert "co_learning" in result
    assert result["co_learning"]["total_causal_events"] > 0
    assert result["co_learning"]["network_maturity"] in ("early", "developing", "converging", "harmony")
    assert len(result["trajectory"][-1]["reasons"]) > 0


def test_mcp_live_model_pilot_subprocess() -> None:
    result = _mcp_call("ls_run_live_model_pilot", {})

    assert result["tool"] == "ls_run_live_model_pilot"
    assert result["metric_version"] == "live_model_pilot.v0.2"
    assert result["mode"] == "sample"
    assert result["summary"]["decision"] == "sample_pipeline_ready"
    assert result["route_event"]["durable_state_written"] is False
    assert result["route_memory"]["version"] == "route_memory.v0"
    assert result["route_memory"]["durable_state_written"] is False
    assert result["multi_actor_route"] is None
    assert result["network_context"]["trajectory_metric_version"] == "network_trajectory.v0.2"
