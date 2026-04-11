from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cognitive_state import CognitiveStateBridge
from .mcp_tools import MCPValidationError
from .runtime.protocol import TaskRuntime


@dataclass(frozen=True)
class ResourceRef:
    uri: str
    name: str


class MCPResourceRegistry:
    """Expose task state as MCP resources."""

    def __init__(
        self,
        task_manager: TaskRuntime,
        cognitive_state: CognitiveStateBridge | None = None,
    ) -> None:
        self.task_manager = task_manager
        self._cognitive_state = cognitive_state or CognitiveStateBridge(task_manager=task_manager)

    def list_resources(self) -> list[ResourceRef]:
        return [
            ResourceRef(uri="task://{id}/status", name="Task status"),
            ResourceRef(uri="task://{id}/trace", name="Task trace"),
            ResourceRef(uri="task://{id}/artifacts", name="Task artifacts"),
            ResourceRef(uri="task://{id}/summary", name="Task summary"),
            ResourceRef(uri="task://{id}/plan", name="Task plan"),
            ResourceRef(uri="task://{id}/approvals", name="Task approvals"),
            ResourceRef(uri="resonance/snapshot", name="Resonance snapshot"),
            ResourceRef(uri="resonance/relational-graph", name="Resonance relational graph"),
            ResourceRef(uri="cognitive/relational-state", name="Cognitive relational state"),
            ResourceRef(uri="alignment/current", name="Current alignment state"),
            ResourceRef(uri="omni/last-insight", name="Last Qwen Omni insight"),
        ]

    def read_resource(self, uri: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        args = arguments or {}
        if uri == "resonance/snapshot":
            return self._cognitive_state.get_resonance_snapshot(
                top_k=int(args.get("top_k", 10)),
                min_resonance_score=float(args.get("min_resonance_score", 0.3)),
            )
        if uri == "resonance/relational-graph":
            return self._cognitive_state.get_relational_graph(
                unit_id=str(args.get("unit_id", "")),
                depth=int(args.get("depth", 2)),
            )
        if uri == "cognitive/relational-state":
            return self._cognitive_state.get_relational_state(
                top_k=int(args.get("top_k", 10)),
                min_resonance_score=float(args.get("min_resonance_score", 0.3)),
            )
        if uri == "alignment/current":
            return self._cognitive_state.get_alignment_current()
        if uri == "omni/last-insight":
            return self._cognitive_state.get_omni_last_insight()

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
