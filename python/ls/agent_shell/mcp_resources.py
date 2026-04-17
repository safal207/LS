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
            ResourceRef(uri="cognitive/relational-why", name="Why two units are linked"),
            ResourceRef(uri="cognitive/relational-suggestion", name="Suggest a relation edge"),
            ResourceRef(uri="alignment/current", name="Current alignment state"),
            ResourceRef(uri="omni/last-insight", name="Last Qwen Omni insight"),
            ResourceRef(uri="self/relational-self", name="Relational Self summary"),
            ResourceRef(uri="self/coherence-history", name="Relational Self coherence history"),
            ResourceRef(uri="self/constitution-status", name="Relational Self constitution status"),
            ResourceRef(uri="self/metrics", name="Relational Self metrics snapshot"),
            ResourceRef(uri="self/action-history", name="Relational Self action history"),
            # Phase 2.4 — Emotional Memory resources
            ResourceRef(uri="self/emotional-memory", name="Emotional memory entries and summary"),
            ResourceRef(uri="self/emotional-arc", name="Emotional bond arc trajectory"),
            ResourceRef(uri="self/emotional-continuity", name="Persistent emotional continuity state"),
            ResourceRef(uri="self/attachment-bond", name="Long-term attachment bond snapshot"),
            ResourceRef(uri="self/emotional-bonding-arc", name="Attachment evolution history"),
            ResourceRef(uri="council/live", name="Current multi-user live council state"),
            ResourceRef(uri="shared-self/current", name="Shared Relational Self snapshot"),
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
        if uri == "cognitive/relational-why":
            return self._cognitive_state.ask_relational_question(
                source_unit_id=str(args.get("source_unit_id", "")),
                target_unit_id=str(args.get("target_unit_id", "")),
            )
        if uri == "cognitive/relational-suggestion":
            return self._cognitive_state.suggest_new_relation(
                source_unit_id=str(args.get("source_unit_id", "")),
                target_unit_id=str(args.get("target_unit_id", "")),
                relation_type=str(args.get("relation_type", "reinforces")),
                strength=float(args.get("strength", 0.5)),
                rationale=str(args.get("rationale", "")),
            )
        if uri == "alignment/current":
            return self._cognitive_state.get_alignment_current()
        if uri == "omni/last-insight":
            return self._cognitive_state.get_omni_last_insight()
        if uri == "self/relational-self":
            return self._cognitive_state.get_relational_self_summary()
        if uri == "self/coherence-history":
            return self._cognitive_state.get_coherence_history(
                limit=int(args.get("limit", 30)),
            )
        if uri == "self/constitution-status":
            return self._cognitive_state.get_constitution_status(
                limit=int(args.get("limit", 20)),
            )
        if uri == "self/metrics":
            return self._cognitive_state.get_self_metrics(
                window=int(args.get("window", 100)),
            )
        if uri == "self/action-history":
            return self._cognitive_state.get_action_history(
                limit=int(args.get("limit", 30)),
            )
        # Phase 2.4 — Emotional Memory resources
        if uri == "self/emotional-memory":
            return self._cognitive_state.get_emotional_memory(
                limit=int(args.get("limit", 50)),
            )
        if uri == "self/emotional-arc":
            return self._cognitive_state.get_emotional_arc(
                limit=int(args.get("limit", 100)),
            )
        if uri == "self/emotional-continuity":
            return self._cognitive_state.get_emotional_continuity()
        if uri == "self/attachment-bond":
            return self._cognitive_state.get_attachment_bond()
        if uri == "self/emotional-bonding-arc":
            return self._cognitive_state.get_emotional_bonding_arc(
                limit=int(args.get("limit", 120)),
            )
        if uri == "council/live":
            return self._cognitive_state.get_live_council_state(
                session_id=str(args.get("session_id", "")),
            )
        if uri == "shared-self/current":
            return self._cognitive_state.get_shared_self_current()

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
