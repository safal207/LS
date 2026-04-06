from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .mcp_tools import MCPValidationError, TaskManager


@dataclass(frozen=True)
class ResourceRef:
    uri: str
    name: str


class MCPResourceRegistry:
    """Expose task state as MCP resources."""

    def __init__(self, task_manager: TaskManager) -> None:
        self.task_manager = task_manager

    def list_resources(self) -> list[ResourceRef]:
        return [
            ResourceRef(uri="task://{id}/status", name="Task status"),
            ResourceRef(uri="task://{id}/trace", name="Task trace"),
            ResourceRef(uri="task://{id}/artifacts", name="Task artifacts"),
            ResourceRef(uri="task://{id}/summary", name="Task summary"),
            ResourceRef(uri="task://{id}/plan", name="Task plan"),
            ResourceRef(uri="task://{id}/approvals", name="Task approvals"),
        ]

    def read_resource(self, uri: str) -> dict[str, Any]:
        task_id, suffix = self._parse_task_uri(uri)

        if suffix == "status":
            return self.task_manager.get_status(task_id=task_id)
        if suffix == "trace":
            payload = self.task_manager.get_trace(task_id=task_id, limit=200)
            task = self.task_manager.get_status(task_id=task_id)
            approval_state = [
                {"step_id": step["id"], "status": step["status"]}
                for step in task["steps"]
                if step["needs_approval"]
            ]
            payload["approvals"] = approval_state
            payload["latest_reasoning_notes"] = [event["message"] for event in payload["events"][-5:]]
            return payload
        if suffix == "artifacts":
            return self.task_manager.list_artifacts(task_id=task_id)
        if suffix == "summary":
            status = self.task_manager.get_status(task_id=task_id)
            return {
                "task_id": task_id,
                "status": status["status"],
                "summary": status["summary"] or "Summary not available yet.",
            }
        if suffix == "plan":
            status = self.task_manager.get_status(task_id=task_id)
            return {
                "task_id": task_id,
                "plan": [step for step in status["steps"]],
            }
        if suffix == "approvals":
            status = self.task_manager.get_status(task_id=task_id)
            return {
                "task_id": task_id,
                "approvals": [
                    {
                        "step_id": step["id"],
                        "title": step["title"],
                        "status": step["status"],
                    }
                    for step in status["steps"]
                    if step["needs_approval"]
                ],
            }
        raise MCPValidationError(f"Unsupported resource URI: {uri}")

    @staticmethod
    def _parse_task_uri(uri: str) -> tuple[str, str]:
        if not uri.startswith("task://"):
            raise MCPValidationError(f"Unsupported resource URI: {uri}")
        body = uri.removeprefix("task://")
        parts = [p for p in body.split("/") if p]
        if len(parts) != 2:
            raise MCPValidationError(f"Unsupported resource URI: {uri}")
        task_id, suffix = parts
        return task_id, suffix
