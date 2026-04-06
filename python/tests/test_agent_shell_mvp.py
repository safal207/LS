import os
import json
from pathlib import Path
import subprocess

from typer.testing import CliRunner

from ls.agent_shell.cli import app
from ls.agent_shell.runtime.task_manager import TaskManager

runner = CliRunner()


def test_plan_only_creates_steps(tmp_path: Path) -> None:
    manager = TaskManager(db_path=tmp_path / "runtime.db", artifacts_root=tmp_path / "artifacts")
    task, plan = manager.plan_only("Create investor opening slide for LS", mode="safe-write")

    assert task.id.startswith("task-")
    assert len(plan) == 5
    assert any(step["needs_approval"] for step in plan)
    assert all(step["id"].startswith(task.id) for step in plan)


def test_two_tasks_in_same_db_have_unique_step_ids(tmp_path: Path) -> None:
    manager = TaskManager(db_path=tmp_path / "runtime.db", artifacts_root=tmp_path / "artifacts")

    first, first_plan = manager.plan_only("Task one", mode="safe-write")
    second, second_plan = manager.plan_only("Task two", mode="safe-write")

    assert first.id != second.id
    first_ids = {step["id"] for step in first_plan}
    second_ids = {step["id"] for step in second_plan}
    assert first_ids.isdisjoint(second_ids)


def test_run_waits_for_approval_and_can_resume(tmp_path: Path) -> None:
    manager = TaskManager(db_path=tmp_path / "runtime.db", artifacts_root=tmp_path / "artifacts")
    task_id = manager.run_task("Review PR #387 and write feedback", mode="safe-write")

    status = manager.get_status(task_id)
    assert status["status"] == "waiting_approval"
    blocked_step = next(step for step in status["steps"] if step["status"] == "waiting_approval")

    manager.approve(task_id, blocked_step["id"])

    resumed = manager.get_status(task_id)
    assert resumed["status"] == "completed"
    artifacts = manager.list_artifacts(task_id)
    assert artifacts


def test_reject_moves_to_blocked(tmp_path: Path) -> None:
    manager = TaskManager(db_path=tmp_path / "runtime.db", artifacts_root=tmp_path / "artifacts")
    task_id = manager.run_task("Draft docs", mode="safe-write")
    status = manager.get_status(task_id)
    blocked_step = next(step for step in status["steps"] if step["status"] == "waiting_approval")

    manager.reject(task_id, blocked_step["id"], "Need diff first")

    status_after = manager.get_status(task_id)
    assert status_after["status"] == "blocked"


def test_reject_then_resume_is_blocked(tmp_path: Path) -> None:
    manager = TaskManager(db_path=tmp_path / "runtime.db", artifacts_root=tmp_path / "artifacts")
    task_id = manager.run_task("Draft docs", mode="safe-write")
    status = manager.get_status(task_id)
    blocked_step = next(step for step in status["steps"] if step["status"] == "waiting_approval")

    manager.reject(task_id, blocked_step["id"], "Need diff first")

    try:
        manager.resume_task(task_id)
        assert False, "resume_task should fail for blocked tasks"
    except ValueError as exc:
        assert "cannot be resumed" in str(exc)


def test_read_only_never_schedules_mutating_steps(tmp_path: Path) -> None:
    manager = TaskManager(db_path=tmp_path / "runtime.db", artifacts_root=tmp_path / "artifacts")
    task, plan = manager.plan_only("Review PR #387 and write feedback", mode="read-only")

    mutating = {"write", "git", "browser", "tool", "artifact"}
    assert task.id.startswith("task-")
    assert plan
    assert not any(step["type"] in mutating for step in plan)


def test_cli_inspect_approve_and_artifacts_flow(tmp_path: Path) -> None:
    runtime_root = tmp_path / ".ls_agent"
    manager = TaskManager(db_path=runtime_root / "runtime.db", artifacts_root=runtime_root / "artifacts")
    task_id = manager.run_task("Prepare docs", mode="safe-write")
    status = manager.get_status(task_id)
    waiting_step = next(step for step in status["steps"] if step["status"] == "waiting_approval")

    inspect_result = runner.invoke(app, ["inspect", task_id, "--runtime-root", str(runtime_root)])
    assert inspect_result.exit_code == 0
    assert "Waiting approval" in inspect_result.stdout
    assert waiting_step["id"] in inspect_result.stdout

    approve_result = runner.invoke(
        app,
        ["approve", task_id, waiting_step["id"], "--runtime-root", str(runtime_root)],
    )
    assert approve_result.exit_code == 0
    assert "Approved" in approve_result.stdout

    artifacts_result = runner.invoke(app, ["artifacts", task_id, "--runtime-root", str(runtime_root)])
    assert artifacts_result.exit_code == 0
    assert "Task report" in artifacts_result.stdout


def test_cli_serve_http_sets_runtime_root(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def _fake_http_server(*, host: str, port: int) -> None:
        captured["host"] = host
        captured["port"] = port
        captured["runtime_root"] = os.environ.get("LS_TASK_RUNTIME_ROOT")

    from ls.agent_shell import cli as cli_module

    monkeypatch.setattr(cli_module, "run_http_server", _fake_http_server)
    result = runner.invoke(
        app,
        [
            "serve",
            "--transport",
            "http",
            "--host",
            "127.0.0.1",
            "--port",
            "8123",
            "--runtime-root",
            str(tmp_path / "custom-root"),
        ],
    )
    assert result.exit_code == 0
    assert "Runtime root:" in result.stdout
    assert captured == {
        "host": "127.0.0.1",
        "port": 8123,
        "runtime_root": str(tmp_path / "custom-root"),
    }


def test_cli_tasks_approvals_and_artifact_views(tmp_path: Path) -> None:
    runtime_root = tmp_path / ".ls_agent"
    manager = TaskManager(db_path=runtime_root / "runtime.db", artifacts_root=runtime_root / "artifacts")
    task_id = manager.run_task("Prepare docs", mode="safe-write")
    status = manager.get_status(task_id)
    waiting_step = next(step for step in status["steps"] if step["status"] == "waiting_approval")

    tasks_result = runner.invoke(
        app,
        ["list", "--status", "waiting_approval", "--runtime-root", str(runtime_root)],
    )
    assert tasks_result.exit_code == 0
    assert task_id in tasks_result.stdout

    approvals_result = runner.invoke(
        app,
        ["approvals", "--task-id", task_id, "--runtime-root", str(runtime_root)],
    )
    assert approvals_result.exit_code == 0
    assert task_id in approvals_result.stdout
    assert "pending" in approvals_result.stdout

    manager.approve(task_id, waiting_step["id"])
    artifact = manager.list_artifacts(task_id)[0]

    artifact_result = runner.invoke(
        app,
        ["artifact", artifact["id"], "--runtime-root", str(runtime_root)],
    )
    assert artifact_result.exit_code == 0
    assert artifact["id"] in artifact_result.stdout
    assert artifact["title"] in artifact_result.stdout


def test_cli_artifact_open_uses_platform_opener(monkeypatch, tmp_path: Path) -> None:
    runtime_root = tmp_path / ".ls_agent"
    manager = TaskManager(db_path=runtime_root / "runtime.db", artifacts_root=runtime_root / "artifacts")
    task_id = manager.run_task("Prepare docs", mode="safe-write")
    status = manager.get_status(task_id)
    waiting_step = next(step for step in status["steps"] if step["status"] == "waiting_approval")
    manager.approve(task_id, waiting_step["id"])
    artifact = manager.list_artifacts(task_id)[0]

    opened: dict[str, str] = {}

    def _fake_open(target: Path) -> None:
        opened["path"] = str(target)

    from ls.agent_shell import cli as cli_module

    monkeypatch.setattr(cli_module, "_open_path", _fake_open)
    result = runner.invoke(
        app,
        ["artifact-open", artifact["id"], "--runtime-root", str(runtime_root)],
    )
    assert result.exit_code == 0
    assert opened["path"].endswith("report.md")
    assert "Opened" in result.stdout


def test_cli_ltp_export_writes_jsonl_trace(tmp_path: Path) -> None:
    runtime_root = tmp_path / ".ls_agent"
    manager = TaskManager(db_path=runtime_root / "runtime.db", artifacts_root=runtime_root / "artifacts")
    task_id = manager.run_task("Prepare docs", mode="safe-write")
    output = tmp_path / "ltp" / "task.trace.jsonl"

    result = runner.invoke(
        app,
        ["ltp-export", task_id, "--runtime-root", str(runtime_root), "--output", str(output)],
    )
    assert result.exit_code == 0
    assert output.exists()
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows
    assert rows[0]["anchors"][0] == f"task:{task_id}"
    assert rows[0]["decision"] in {"admissible", "drift", "rejected"}


def test_cli_ltp_inspect_uses_external_ltp_tool(monkeypatch, tmp_path: Path) -> None:
    runtime_root = tmp_path / ".ls_agent"
    manager = TaskManager(db_path=runtime_root / "runtime.db", artifacts_root=runtime_root / "artifacts")
    task_id = manager.run_task("Prepare docs", mode="safe-write")
    fake_repo = tmp_path / "_lthread_proto"
    fake_repo.mkdir()
    captured: dict[str, object] = {}

    def _fake_run(trace_file: Path, *, ltp_repo_root: Path) -> subprocess.CompletedProcess[str]:
        captured["trace_file"] = str(trace_file)
        captured["ltp_repo_root"] = str(ltp_repo_root)
        lines = trace_file.read_text(encoding="utf-8").splitlines()
        captured["lines"] = len(lines)
        return subprocess.CompletedProcess(
            args=["pnpm"],
            returncode=0,
            stdout="LTP inspector ok\nRouting Decisions: Executed=1 Deferred=0 Replayed=0 Frozen=0\n",
            stderr="",
        )

    from ls.agent_shell import cli as cli_module

    monkeypatch.setattr(cli_module, "_run_ltp_inspect", _fake_run)
    result = runner.invoke(
        app,
        ["ltp-inspect", task_id, "--runtime-root", str(runtime_root), "--ltp-repo-root", str(fake_repo)],
    )
    assert result.exit_code == 0
    assert "LTP inspector ok" in result.stdout
    assert captured["ltp_repo_root"] == str(fake_repo)
    assert int(captured["lines"]) >= 1
