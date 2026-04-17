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
            "get_relational_insight": self._get_relational_insight,
            "ask_self": self._ask_self,
            "rollback_self_action": self._rollback_self_action,
            # Phase 2.4
            "get_emotional_insight": self._get_emotional_insight,
            "get_attachment_insight": self._get_attachment_insight,
            # Phase 3.0 starter
            "propose_shared_insight": self._propose_shared_insight,
            "accept_shared_self": self._accept_shared_self,
            "join_live_council": self._join_live_council,
        }

    def list_tools(self) -> list[dict[str, Any]]:
        return [{"name": name} for name in self._tools]

    @property
    def cognitive_state(self) -> CognitiveStateBridge:
        return self._cognitive_state

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

    def _get_relational_insight(self, args: dict[str, Any]) -> dict[str, Any]:
        """Return relational subgraph for a given unit_id.

        The graph reveals *why* two cognitive routes are connected — useful for
        external tools (Cursor, Claude Desktop) to inspect how the agent's
        thinking evolves through relational links.

        Args:
            unit_id: ID of the ResonanceKnowledgeUnit to start from.
            depth:   BFS hop depth (default 2).
        """
        unit_id = str(args.get("unit_id", ""))
        depth = int(args.get("depth", 2))
        return self._cognitive_state.get_relational_graph(unit_id=unit_id, depth=depth)

    def _ask_self(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._cognitive_state.ask_self(str(args.get("question", "")))

    def _rollback_self_action(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._cognitive_state.rollback_self_action(
            action_id=str(args.get("action_id", "")),
        )

    def _get_emotional_insight(self, args: dict[str, Any]) -> dict[str, Any]:
        """Answer an emotionally-framed question about the relational bond.

        Args:
            question: Natural-language question about the emotional relationship.
            limit:    Number of supporting entries to include (default 10).
        """
        question = str(args.get("question", ""))
        limit = int(args.get("limit", 10))
        return self._cognitive_state.get_emotional_insight(question, limit=limit)

    def _get_attachment_insight(self, args: dict[str, Any]) -> dict[str, Any]:
        question = str(args.get("question", ""))
        window = int(args.get("window", 60))
        return self._cognitive_state.get_attachment_insight(question, window=window)

    def _propose_shared_insight(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._cognitive_state.propose_shared_insight(
            recipient=str(args.get("recipient", "")),
            source_node_id=str(args.get("source_node_id", "")),
            target_node_id=str(args.get("target_node_id", "")),
            relation_type=str(args.get("relation_type", "reinforces")),
            strength=float(args.get("strength", 0.5)),
            rationale=str(args.get("rationale", "")),
        )

    def _accept_shared_self(self, args: dict[str, Any]) -> dict[str, Any]:
        payload = args.get("shared_payload")
        if not isinstance(payload, dict):
            raise MCPValidationError("shared_payload must be an object")
        return self._cognitive_state.accept_shared_self(
            payload,
            selective_merge=bool(args.get("selective_merge", True)),
        )

    def _join_live_council(self, args: dict[str, Any]) -> dict[str, Any]:
        from modules.graph.memory_store import MemoryGraphStore

        session_id = str(args.get("session_id", "")).strip()
        participant_id = str(args.get("participant_id", "local")).strip() or "local"
        consent = bool(args.get("consent", True))
        if not session_id:
            raise MCPValidationError("session_id is required")

        store = MemoryGraphStore(self._cognitive_state._store_path)  # noqa: SLF001
        current = store.get_live_council_state()
        participants = list(current.get("participants") or [])
        if consent and participant_id not in participants:
            participants.append(participant_id)
        if not consent and participant_id in participants:
            participants.remove(participant_id)

        payload = {
            "session_id": session_id,
            "mode": "multi-user-live",
            "status": "active" if participants else "idle",
            "participants": participants,
            "shared_emotional_summary": self._cognitive_state.get_emotional_continuity(),
        }
        saved = store.save_live_council_state(payload)
        store.append_live_council_audit(
            {
                "event": "join_live_council",
                "session_id": session_id,
                "participant_id": participant_id,
                "consent": consent,
            }
        )
        return {
            "resource": "council/live",
            "joined": consent,
            "session": saved,
        }


def tool_call_from_json(registry: MCPToolRegistry, raw: str) -> str:
    payload = json.loads(raw)
    result = registry.call_tool(payload["tool"], payload.get("arguments", {}))
    return json.dumps({"result": result}, ensure_ascii=False)
