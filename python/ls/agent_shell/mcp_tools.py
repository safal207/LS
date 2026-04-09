from __future__ import annotations

from typing import Any
import json

from .cognitive_state import CognitiveStateBridge
from .runtime.factory import RuntimeBindingError, resolve_task_runtime
from .runtime.protocol import TaskRuntime


class MCPValidationError(ValueError):
    """MCP-facing validation error."""


class MCPToolRegistry:
    """Thin MCP tool adapter over an externally bound TaskRuntime."""

    def __init__(
        self,
        task_manager: TaskRuntime | None = None,
        cognitive_state: CognitiveStateBridge | None = None,
    ) -> None:
        self.task_manager = task_manager or resolve_task_runtime()
        self._cognitive_state = cognitive_state or CognitiveStateBridge(task_manager=self.task_manager)
        self._tools = {
            "ls_plan_task": self._plan_task,
            "ls_run_task": self._run_task,
            "ls_resume_task": self._resume_task,
            "ls_get_status": self._get_status,
            "ls_get_trace": self._get_trace,
            "ls_list_artifacts": self._list_artifacts,
            "ls_approve": self._approve,
            "ls_reject": self._reject,
            "get_cognitive_state": self._get_cognitive_state,
        }

    def list_tools(self) -> list[dict[str, Any]]:
        return [{"name": name} for name in self._tools]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in self._tools:
            raise MCPValidationError(f"Unknown tool: {name}")
        try:
            return self._tools[name](arguments)
        except (RuntimeBindingError, ValueError) as exc:
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

    def _get_cognitive_state(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._cognitive_state.get_cognitive_state(
            top_k=int(args.get("top_k", 10)),
            min_resonance_score=float(args.get("min_resonance_score", 0.3)),
        )


def tool_call_from_json(registry: MCPToolRegistry, raw: str) -> str:
    payload = json.loads(raw)
    result = registry.call_tool(payload["tool"], payload.get("arguments", {}))
    return json.dumps({"result": result}, ensure_ascii=False)
