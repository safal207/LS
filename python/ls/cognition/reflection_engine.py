from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from ls.cognition.state_tracker import AgentState, StateTracker
from ls.memory.edge import MemoryEdge
from ls.memory.graph_store import JsonGraphStore
from ls.memory.memory_graph import MemoryGraph


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReflectionResult:
    progress: float
    reason: str
    previous_state: AgentState
    current_state: AgentState
    reflection_node_id: str


class ReflectionEngine:
    """Cognitive loop engine: state diff -> progress -> reflection -> memory graph update."""

    def __init__(
        self,
        memory_graph: MemoryGraph,
        state_tracker: StateTracker | None = None,
        event_bus: Any | None = None,
        graph_store: JsonGraphStore | None = None,
    ):
        self.memory_graph = memory_graph
        self.state_tracker = state_tracker or StateTracker()
        self.graph_store = graph_store
        self._last_nodes: dict[str, str] = {}

        if event_bus is not None:
            event_bus.subscribe("decision_made", self.process)
            event_bus.subscribe("tool_executed", self.process)
            event_bus.subscribe("action_result", self.process)

    def process(self, event: Any) -> ReflectionResult | None:
        payload = dict(getattr(event, "payload", {}) or {})
        previous = self.state_tracker.current_state()

        current = AgentState(
            goal=str(payload.get("goal", previous.goal if previous else "unspecified_goal")),
            context=dict(payload.get("context", {})),
            progress_score=float(payload.get("progress_score", 0.0)),
            goal_completion=float(payload.get("goal_completion", payload.get("completion", 0.0))),
        )
        self.state_tracker.update(current)

        if previous is None:
            logger.info("[ReflectionEngine] bootstrap state recorded")
            self._create_state_node(current)
            self._persist_if_needed()
            return None

        result = self.reflect(previous, current)
        self._persist_if_needed()
        return result

    def reflect(self, previous_state: AgentState, current_state: AgentState) -> ReflectionResult:
        progress = self.compute_progress(previous_state, current_state)
        reason = self.generate_reflection(previous_state, current_state, progress)

        event_node = self.memory_graph.add_node(node_type="event", content={"context": current_state.context})
        decision_node = self.memory_graph.add_node(node_type="decision", content={"goal": current_state.goal})
        action_node = self.memory_graph.add_node(node_type="action", content={"action": current_state.context.get("action", "unknown")})
        result_node = self.memory_graph.add_node(node_type="knowledge", content={"result": current_state.context.get("result", "unknown")})
        reflection_node = self.memory_graph.add_node(
            node_type="reflection",
            content={
                "reason": reason,
                "progress": progress,
                "goal": current_state.goal,
            },
        )

        self.memory_graph.add_edge(MemoryEdge(event_node.node_id, decision_node.node_id, "leads_to", 1.0))
        self.memory_graph.add_edge(MemoryEdge(decision_node.node_id, action_node.node_id, "leads_to", 1.0))
        self.memory_graph.add_edge(MemoryEdge(action_node.node_id, result_node.node_id, "derived_from", 1.0))
        self.memory_graph.add_edge(MemoryEdge(result_node.node_id, reflection_node.node_id, "related_to", 1.0))
        self.memory_graph.add_edge(MemoryEdge(reflection_node.node_id, decision_node.node_id, "improves" if progress >= 0 else "worsens", progress))

        state_node = self._create_state_node(current_state)
        self.memory_graph.add_edge(MemoryEdge(state_node.node_id, reflection_node.node_id, "related_to", 1.0))

        logger.info("[ReflectionEngine] progress %+0.3f", progress)
        logger.info("[MemoryGraph] node added: reflection")

        return ReflectionResult(
            progress=progress,
            reason=reason,
            previous_state=previous_state,
            current_state=current_state,
            reflection_node_id=reflection_node.node_id,
        )

    @staticmethod
    def compute_progress(previous_state: AgentState, current_state: AgentState) -> float:
        return current_state.goal_completion - previous_state.goal_completion

    @staticmethod
    def generate_reflection(previous_state: AgentState, current_state: AgentState, progress: float) -> str:
        if progress > 0:
            trend = "closer"
        elif progress < 0:
            trend = "farther"
        else:
            trend = "unchanged"
        return (
            f"Goal '{current_state.goal}' moved {trend}: "
            f"completion {previous_state.goal_completion:.2f} -> {current_state.goal_completion:.2f}."
        )

    def _create_state_node(self, state: AgentState):
        node = self.memory_graph.add_node(
            node_type="agent_state",
            content={
                "goal": state.goal,
                "goal_completion": state.goal_completion,
                "progress_score": state.progress_score,
                "context": state.context,
            },
        )

        previous_state_node_id = self._last_nodes.get("agent_state")
        if previous_state_node_id and previous_state_node_id in self.memory_graph.nodes:
            delta = state.progress_score
            relation = "improves" if delta >= 0 else "worsens"
            self.memory_graph.add_edge(MemoryEdge(previous_state_node_id, node.node_id, relation, delta))
            logger.info("[ReflectionEngine] state transition %s -> %s", previous_state_node_id, node.node_id)

        self._last_nodes["agent_state"] = node.node_id
        return node

    def _persist_if_needed(self) -> None:
        if self.graph_store is None:
            return
        self.graph_store.save(self.memory_graph.to_dict())
