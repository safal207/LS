from __future__ import annotations

from typing import Any
import json

from .runtime import RuntimeValidationError
from .runtime.factory import resolve_task_runtime
from .runtime.protocol import TaskRuntime


class MCPValidationError(RuntimeValidationError):
    """MCP-facing validation error."""


class MCPToolRegistry:
    """Thin MCP tool adapter over the authoritative TaskManager runtime."""

    def __init__(self, task_manager: TaskRuntime | None = None) -> None:
        self.task_manager = task_manager or resolve_task_runtime()
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
        try:
            return self._tools[name](arguments)
        except RuntimeValidationError as exc:
            raise MCPValidationError(str(exc)) from exc

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
