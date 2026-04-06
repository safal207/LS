from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import uuid


ALLOWED_MODES = {"read-only", "safe-write", "blocked"}


class MCPValidationError(ValueError):
    """Raised when an MCP payload is invalid."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class Step:
    id: str
    title: str
    type: str
    needs_approval: bool
    reason: str
    status: str = "pending"


@dataclass
class Artifact:
    id: str
    title: str
    type: str
    path_or_url: str


@dataclass
class Task:
    id: str
    prompt: str
    mode: str
    status: str
    steps: list[Step] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    summary: str | None = None


class TaskManager:
    """Small in-process task manager used by the MCP façade."""

    def __init__(self, artifact_root: str | Path = ".ls_agent/artifacts") -> None:
        self._tasks: dict[str, Task] = {}
        self._artifact_root = Path(artifact_root)

    def _validate_mode(self, mode: str) -> None:
        if mode not in ALLOWED_MODES:
            raise MCPValidationError(f"Unknown mode: {mode}")

    @staticmethod
    def _task_id() -> str:
        return f"task-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _artifact_id() -> str:
        return f"artifact-{uuid.uuid4().hex[:8]}"

    def _validate_task_step(self, task_id: str, step_id: str | None = None) -> Task:
        task = self._tasks.get(task_id)
        if not task:
            raise MCPValidationError(f"Unknown task_id: {task_id}")
        if step_id is not None and not any(step.id == step_id for step in task.steps):
            raise MCPValidationError(f"Unknown step_id: {step_id}")
        return task

    def _add_trace(self, task: Task, level: str, message: str, step_id: str | None = None) -> None:
        task.trace.append(
            {
                "created_at": _now_iso(),
                "level": level,
                "step_id": step_id,
                "message": message,
            }
        )

    def plan_task(self, *, prompt: str, mode: str) -> dict[str, Any]:
        self._validate_mode(mode)
        task_id = self._task_id()
        step = Step(
            id=f"{task_id}-step-1",
            title="Fetch task context",
            type="read",
            needs_approval=False,
            reason="Need source context before analysis.",
            status="pending",
        )
        task = Task(id=task_id, prompt=prompt, mode=mode, status="blocked", steps=[step])
        self._add_trace(task, "info", f"Plan generated for {task_id}", step.id)
        self._tasks[task_id] = task
        return {
            "task_id": task_id,
            "status": task.status,
            "plan": [self._serialize_step(step)],
            "summary": "Plan generated only.",
        }

    def run_task(self, *, prompt: str, mode: str) -> dict[str, Any]:
        self._validate_mode(mode)
        task_id = self._task_id()
        steps = [
            Step(
                id=f"{task_id}-step-1",
                title="Read relevant docs",
                type="read",
                needs_approval=False,
                reason="Collect local context first.",
                status="pending",
            ),
            Step(
                id=f"{task_id}-step-2",
                title="Draft execution output",
                type="reason",
                needs_approval=False,
                reason="Prepare bounded advisory output.",
                status="pending",
            ),
            Step(
                id=f"{task_id}-step-3",
                title="Apply write action",
                type="write",
                needs_approval=True,
                reason="Write-side effects require explicit approval.",
                status="pending",
            ),
        ]
        task = Task(id=task_id, prompt=prompt, mode=mode, status="running", steps=steps)
        self._tasks[task_id] = task

        for step in steps[:2]:
            step.status = "completed"
            self._add_trace(task, "info", f"Running {step.id}: {step.title}", step.id)

        approval_step = steps[2]
        task.status = "waiting_approval"
        approval_step.status = "waiting_approval"
        self._add_trace(task, "info", f"Approval required for {approval_step.id}", approval_step.id)

        return {
            "task_id": task_id,
            "status": task.status,
            "next_action": "approval_required",
            "current_step_id": approval_step.id,
        }

    def resume_task(self, *, task_id: str) -> dict[str, Any]:
        task = self._validate_task_step(task_id)
        if task.status == "blocked":
            raise MCPValidationError("Cannot resume blocked task without explicit override flow")
        if task.status == "waiting_approval":
            raise MCPValidationError("Cannot resume while waiting approval; use ls_approve or ls_reject")
        task.status = "running"
        self._add_trace(task, "info", f"Task {task_id} resumed")
        return {"task_id": task_id, "status": task.status}

    def get_status(self, *, task_id: str) -> dict[str, Any]:
        task = self._validate_task_step(task_id)
        return {
            "task_id": task.id,
            "mode": task.mode,
            "status": task.status,
            "summary": task.summary,
            "steps": [self._serialize_step(s) for s in task.steps],
        }

    def get_trace(self, *, task_id: str, limit: int = 100) -> dict[str, Any]:
        task = self._validate_task_step(task_id)
        sanitized_limit = max(1, min(limit, 500))
        return {
            "task_id": task.id,
            "events": task.trace[-sanitized_limit:],
        }

    def list_artifacts(self, *, task_id: str) -> dict[str, Any]:
        task = self._validate_task_step(task_id)
        return {
            "task_id": task.id,
            "artifacts": [a.__dict__.copy() for a in task.artifacts],
        }

    def approve(self, *, task_id: str, step_id: str) -> dict[str, Any]:
        task = self._validate_task_step(task_id, step_id)
        step = next(s for s in task.steps if s.id == step_id)
        if not step.needs_approval:
            raise MCPValidationError("Approval is only valid for approval-gated steps")
        if step.status not in {"waiting_approval", "pending"}:
            raise MCPValidationError("Step is not waiting for approval")

        step.status = "approved"
        self._add_trace(task, "info", f"Approved {step.id}", step.id)
        step.status = "completed"

        task.status = "completed"
        artifact_path = self._artifact_root / task.id / "report.md"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        report = f"# Task report\n\nTask: {task.id}\n\nPrompt: {task.prompt}\n"
        artifact_path.write_text(report, encoding="utf-8")
        task.artifacts.append(
            Artifact(
                id=self._artifact_id(),
                title="Task report",
                type="report",
                path_or_url=str(artifact_path),
            )
        )
        task.summary = "Task completed with approved side effects; artifact created."
        self._add_trace(task, "info", f"Task {task.id} completed", step.id)
        return {"task_id": task.id, "step_id": step.id, "status": "approved"}

    def reject(self, *, task_id: str, step_id: str, reason: str) -> dict[str, Any]:
        task = self._validate_task_step(task_id, step_id)
        step = next(s for s in task.steps if s.id == step_id)
        if not step.needs_approval:
            raise MCPValidationError("Rejection is only valid for approval-gated steps")
        step.status = "rejected"
        task.status = "blocked"
        self._add_trace(task, "warning", f"Rejected {step.id}: {reason}", step.id)
        task.summary = f"Task blocked after rejection: {reason}"
        return {"task_id": task.id, "step_id": step.id, "status": "rejected"}

    @staticmethod
    def _serialize_step(step: Step) -> dict[str, Any]:
        return {
            "id": step.id,
            "title": step.title,
            "type": step.type,
            "status": step.status,
            "needs_approval": step.needs_approval,
            "reason": step.reason,
        }


class MCPToolRegistry:
    """Dispatches MCP tool calls to TaskManager methods."""

    def __init__(self, task_manager: TaskManager | None = None) -> None:
        self.task_manager = task_manager or TaskManager()
        self._tools = {
            "ls_plan_task": self._plan_task,
            "ls_run_task": self._run_task,
            "ls_resume_task": self._resume_task,
            "ls_get_status": self._get_status,
            "ls_get_trace": self._get_trace,
            "ls_list_artifacts": self._list_artifacts,
            "ls_approve": self._approve,
            "ls_reject": self._reject,
        }

    def list_tools(self) -> list[dict[str, Any]]:
        return [{"name": name} for name in self._tools]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in self._tools:
            raise MCPValidationError(f"Unknown tool: {name}")
        return self._tools[name](arguments)

    def _plan_task(self, args: dict[str, Any]) -> dict[str, Any]:
        return self.task_manager.plan_task(prompt=str(args["prompt"]), mode=str(args["mode"]))

    def _run_task(self, args: dict[str, Any]) -> dict[str, Any]:
        return self.task_manager.run_task(prompt=str(args["prompt"]), mode=str(args["mode"]))

    def _resume_task(self, args: dict[str, Any]) -> dict[str, Any]:
        return self.task_manager.resume_task(task_id=str(args["task_id"]))

    def _get_status(self, args: dict[str, Any]) -> dict[str, Any]:
        return self.task_manager.get_status(task_id=str(args["task_id"]))

    def _get_trace(self, args: dict[str, Any]) -> dict[str, Any]:
        limit = int(args.get("limit", 100))
        return self.task_manager.get_trace(task_id=str(args["task_id"]), limit=limit)

    def _list_artifacts(self, args: dict[str, Any]) -> dict[str, Any]:
        return self.task_manager.list_artifacts(task_id=str(args["task_id"]))

    def _approve(self, args: dict[str, Any]) -> dict[str, Any]:
        return self.task_manager.approve(task_id=str(args["task_id"]), step_id=str(args["step_id"]))

    def _reject(self, args: dict[str, Any]) -> dict[str, Any]:
        return self.task_manager.reject(
            task_id=str(args["task_id"]),
            step_id=str(args["step_id"]),
            reason=str(args.get("reason", "No reason provided")),
        )


def tool_call_from_json(registry: MCPToolRegistry, raw: str) -> str:
    payload = json.loads(raw)
    result = registry.call_tool(payload["tool"], payload.get("arguments", {}))
    return json.dumps({"result": result}, ensure_ascii=False)
