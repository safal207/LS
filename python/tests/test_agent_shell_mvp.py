from pathlib import Path

from ls.agent_shell.runtime.task_manager import TaskManager


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
