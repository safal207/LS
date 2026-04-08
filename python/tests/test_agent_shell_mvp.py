from pathlib import Path

from ls.agent_shell.runtime.task_manager import TaskManager
from typer.testing import CliRunner

from ls.agent_shell import cli
from ls.agent_shell.cli import app


def test_plan_only_creates_steps(tmp_path: Path) -> None:
    manager = TaskManager(db_path=tmp_path / "runtime.db", artifacts_root=tmp_path / "artifacts")
    task, plan = manager.plan_only("Сделай investor opening slide для LS", mode="safe-write")

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
    task_id = manager.run_task("Проверь PR #387 и дай review", mode="safe-write")

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
    task, plan = manager.plan_only("Проверь PR #387 и дай review", mode="read-only")

    mutating = {"write", "git", "browser", "tool", "artifact"}
    assert task.id.startswith("task-")
    assert plan
    assert not any(step["type"] in mutating for step in plan)


def test_council_cycle_cli_emits_ledger_artifact(tmp_path: Path) -> None:
    runner = CliRunner()
    artifact_dir = tmp_path / "council-ledger"

    result = runner.invoke(
        app,
        [
            "council-cycle",
            "Help the operator align the council response",
            "--llm-mode",
            "dry-run",
            "--artifact-dir",
            str(artifact_dir),
            "--orientation",
            "test-coordination",
        ],
    )

    assert result.exit_code == 0
    assert "Council cycle:" in result.stdout
    assert "Ledger artifact:" in result.stdout
    artifacts = list(artifact_dir.glob("*.json"))
    assert artifacts


def test_council_cycle_cli_can_publish_to_liminalqa(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    artifact_dir = tmp_path / "council-ledger"

    def fake_publish(ledger: dict) -> tuple[int, object]:
        assert ledger["cycle_id"]
        return 200, {"ok": True, "message": "published"}

    monkeypatch.setattr(cli, "publish_council_ledger_to_liminalqa", fake_publish)

    result = runner.invoke(
        app,
        [
            "council-cycle",
            "Publish this council cycle",
            "--llm-mode",
            "dry-run",
            "--artifact-dir",
            str(artifact_dir),
            "--publish-to-liminalqa",
        ],
    )

    assert result.exit_code == 0
    assert "LiminalQA publish:" in result.stdout
    assert "HTTP 200" in result.stdout


def test_council_cycle_cli_can_use_local_llm_mode(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    artifact_dir = tmp_path / "council-ledger"

    def fake_llm(_user: str, _system: str) -> str:
        return "Local council answer"

    monkeypatch.setattr(cli, "build_local_council_llm_fn", lambda: fake_llm)

    result = runner.invoke(
        app,
        [
            "council-cycle",
            "Use a real local council cycle",
            "--llm-mode",
            "local",
            "--artifact-dir",
            str(artifact_dir),
        ],
    )

    assert result.exit_code == 0
    assert "Council cycle:" in result.stdout
    assert "Ledger artifact:" in result.stdout
    artifacts = list(artifact_dir.glob("*.json"))
    assert artifacts
