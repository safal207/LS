from __future__ import annotations

from importlib import import_module
import os
from pathlib import Path
from typing import Any


# Ordered bindings to the authoritative shell runtime lineage.
# Rebase can keep/adjust this list without touching MCP façade code.
SHELL_RUNTIME_CANDIDATES = (
    "ls.agent_shell.core.runtime:build_runtime",
)


def _load_callable(target: str) -> Any:
    module_name, _, attr = target.partition(":")
    module = import_module(module_name)
    return getattr(module, attr)


def _default_shell_home() -> Path:
    return Path(os.getenv("LS_TASK_RUNTIME_ROOT", ".ls_agent"))


class ShellTaskRuntimeAdapter:
    """Adapt the authoritative TaskManager to the MCP TaskRuntime protocol."""

    def __init__(self, manager: Any) -> None:
        self.manager = manager

    def plan_task(self, *, prompt: str, mode: str) -> dict[str, Any]:
        task, plan = self.manager.plan_only(prompt=prompt, mode=mode)
        return {
            "task_id": task.id,
            "status": "blocked",
            "plan": plan,
            "summary": "Plan generated only.",
        }

    def run_task(self, *, prompt: str, mode: str) -> dict[str, Any]:
        task_id = self.manager.run_task(prompt=prompt, mode=mode)
        status = self.manager.get_status(task_id)
        waiting = next(
            (step for step in status["steps"] if step["status"] == "waiting_approval"),
            None,
        )
        response = {
            "task_id": task_id,
            "status": status["status"],
        }
        if waiting is not None:
            response["next_action"] = "approval_required"
            response["current_step_id"] = waiting["id"]
        return response

    def resume_task(self, *, task_id: str) -> dict[str, Any]:
        self.manager.resume_task(task_id)
        status = self.manager.get_status(task_id)
        return {"task_id": task_id, "status": status["status"]}

    def get_status(self, *, task_id: str) -> dict[str, Any]:
        status = self.manager.get_status(task_id)
        return {
            "task_id": task_id,
            "mode": status["mode"],
            "status": status["status"],
            "summary": status.get("summary"),
            "steps": status["steps"],
        }

    def get_trace(self, *, task_id: str, limit: int = 100) -> dict[str, Any]:
        limit = max(1, min(limit, 500))
        return {"task_id": task_id, "events": self.manager.get_trace(task_id)[-limit:]}

    def list_artifacts(self, *, task_id: str) -> dict[str, Any]:
        return {"task_id": task_id, "artifacts": self.manager.list_artifacts(task_id)}

    def approve(self, *, task_id: str, step_id: str) -> dict[str, Any]:
        self.manager.approve(task_id, step_id)
        return {"task_id": task_id, "step_id": step_id, "status": "approved"}

    def reject(self, *, task_id: str, step_id: str, reason: str) -> dict[str, Any]:
        self.manager.reject(task_id, step_id, reason)
        return {"task_id": task_id, "step_id": step_id, "status": "rejected"}


def _build_task_manager_runtime() -> Any:
    from ls.agent_shell.runtime.task_manager import TaskManager

    home = _default_shell_home()
    manager = TaskManager(db_path=home / "runtime.db", artifacts_root=home / "artifacts")
    return ShellTaskRuntimeAdapter(manager)


def build_shell_runtime() -> Any:
    errors: list[str] = []
    try:
        return _build_task_manager_runtime()
    except Exception as exc:
        errors.append(f"ls.agent_shell.runtime.task_manager:TaskManager -> {exc}")
    for target in SHELL_RUNTIME_CANDIDATES:
        try:
            candidate = _load_callable(target)
            runtime = candidate() if callable(candidate) else candidate
            return runtime
        except Exception as exc:
            errors.append(f"{target} -> {exc}")
    details = "; ".join(errors) if errors else "no candidates configured"
    raise ValueError(f"Could not bind shell runtime. Tried: {details}")
