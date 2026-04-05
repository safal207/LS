from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ls.agent_shell.runtime.approval_manager import ApprovalManager
from ls.agent_shell.runtime.artifact_manager import ArtifactManager
from ls.agent_shell.runtime.executor import Executor
from ls.agent_shell.runtime.planner import Planner
from ls.agent_shell.runtime.trace_store import TraceStore
from ls.agent_shell.schemas.task import Task
from ls.agent_shell.storage.sqlite_store import SQLiteStore, from_json, to_json


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskManager:
    def __init__(self, db_path: Path, artifacts_root: Path):
        self.store = SQLiteStore(db_path)
        self.trace = TraceStore(self.store)
        self.approvals = ApprovalManager(self.store)
        self.artifacts = ArtifactManager(self.store, artifacts_root)
        self.planner = Planner()
        self.executor = Executor(self.store, self.approvals, self.artifacts, self.trace)

    def create_task(self, prompt: str, mode: str) -> Task:
        task_id = f"task-{uuid4().hex[:8]}"
        title = prompt[:80]
        task = Task(id=task_id, title=title, prompt=prompt, mode=mode, status="queued")
        self.store.insert("tasks", asdict(task))
        self.trace.log(task_id, f"Task created in mode={mode}")
        return task

    def build_plan(self, task_id: str) -> list[dict]:
        task = self.store.fetch_one("SELECT * FROM tasks WHERE id=:task_id", task_id=task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        self.store.update("tasks", "id", task_id, status="planning", updated_at=utc_now())
        steps = self.planner.build_plan(task_id, task["prompt"], task["mode"])
        for step in steps:
            payload = asdict(step)
            payload["needs_approval"] = 1 if payload["needs_approval"] else 0
            payload["inputs_json"] = to_json(payload.pop("inputs"))
            payload["outputs_json"] = to_json(payload.pop("outputs"))
            self.store.insert("steps", payload)
        self.trace.log(task_id, f"Built plan with {len(steps)} steps.")
        return [asdict(step) for step in steps]

    def plan_only(self, prompt: str, mode: str) -> tuple[Task, list[dict]]:
        task = self.create_task(prompt, mode)
        plan = self.build_plan(task.id)
        self.store.update("tasks", "id", task.id, status="blocked", updated_at=utc_now(), summary="Plan generated only.")
        return task, plan

    def run_task(self, prompt: str, mode: str) -> str:
        task = self.create_task(prompt, mode)
        self.build_plan(task.id)
        self.executor.run(task.id, mode)
        return task.id

    def resume_task(self, task_id: str) -> None:
        task = self.store.fetch_one("SELECT * FROM tasks WHERE id=:task_id", task_id=task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        self.executor.run(task_id, task["mode"])

    def approve(self, task_id: str, step_id: str) -> None:
        approval = self.store.fetch_one(
            "SELECT * FROM approvals WHERE task_id=:task_id AND step_id=:step_id AND status='pending' ORDER BY created_at DESC LIMIT 1",
            task_id=task_id,
            step_id=step_id,
        )
        if not approval:
            raise ValueError("Pending approval not found")
        self.approvals.set_status(approval["id"], "approved")
        self.executor.resume_after_approval(task_id, step_id)
        self.resume_task(task_id)

    def reject(self, task_id: str, step_id: str, reason: str) -> None:
        approval = self.store.fetch_one(
            "SELECT * FROM approvals WHERE task_id=:task_id AND step_id=:step_id AND status='pending' ORDER BY created_at DESC LIMIT 1",
            task_id=task_id,
            step_id=step_id,
        )
        if not approval:
            raise ValueError("Pending approval not found")
        self.approvals.set_status(approval["id"], "rejected")
        self.store.update("steps", "id", step_id, status="failed")
        self.store.update("tasks", "id", task_id, status="blocked", summary=f"Rejected: {reason}", updated_at=utc_now())
        self.trace.log(task_id, f"Approval rejected for {step_id}: {reason}", level="warning", step_id=step_id)

    def get_status(self, task_id: str) -> dict:
        task = self.store.fetch_one("SELECT * FROM tasks WHERE id=:task_id", task_id=task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        task["steps"] = self.store.fetch_all(
            "SELECT id, title, type, status, needs_approval FROM steps WHERE task_id=:task_id ORDER BY id ASC",
            task_id=task_id,
        )
        return task

    def list_artifacts(self, task_id: str) -> list[dict]:
        return self.store.fetch_all(
            "SELECT id, type, title, path_or_url, created_at FROM artifacts WHERE task_id=:task_id ORDER BY created_at ASC",
            task_id=task_id,
        )

    def get_trace(self, task_id: str) -> list[dict]:
        return self.trace.list_logs(task_id)

    def list_tasks(self) -> list[dict]:
        return self.store.fetch_all(
            "SELECT id, title, mode, status, created_at, updated_at FROM tasks ORDER BY created_at DESC"
        )
