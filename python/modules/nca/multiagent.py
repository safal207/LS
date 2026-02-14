from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .agent import NCAAgent
from .shared_causal import SharedCausalGraph
from .signals import CollectiveSignalBus, InternalSignal


@dataclass
class MultiAgentSystem:
    """Coordinates many NCA agents over a shared causal and signaling layer."""

    agents: list[NCAAgent] = field(default_factory=list)
    shared_causal_graph: SharedCausalGraph = field(default_factory=SharedCausalGraph)
    collective_signal_bus: CollectiveSignalBus = field(default_factory=CollectiveSignalBus)

    def add_agent(self, agent: NCAAgent, *, agent_id: str | None = None) -> None:
        resolved_id = agent_id or getattr(agent.orientation, "identity", None) or f"agent-{len(self.agents)}"
        setattr(agent, "agent_id", resolved_id)
        self.agents.append(agent)
        self.collective_signal_bus.subscribe_agent(resolved_id, agent._orientation_signal_handler)

    def broadcast_signals(self) -> list[dict[str, Any]]:
        distributed: list[dict[str, Any]] = []
        for agent in self.agents:
            agent_id = getattr(agent, "agent_id", "unknown")
            pending = agent.signal_bus.get_recent(clear=True)
            for signal in pending:
                payload = dict(signal.payload)
                payload["sourceagentid"] = agent_id
                collective_signal = InternalSignal(signal_type=signal.signal_type, payload=payload, t=signal.t)
                self.collective_signal_bus.emit_broadcast(collective_signal)
                distributed.append({"sourceagentid": agent_id, "type": signal.signal_type, "payload": payload})
        return distributed

    def step_all(self) -> list[dict[str, Any]]:
        step_events: list[dict[str, Any]] = []
        prior_collective = self.collective_state()
        for agent in self.agents:
            agent.collective_state = prior_collective
            event = agent.step()
            agent_id = getattr(agent, "agent_id", "unknown")
            self.shared_causal_graph.merge(agent.causal_graph, agent_id=agent_id)
            step_events.append({"agent_id": agent_id, **event})

        distributed = self.broadcast_signals()
        collective = self.collective_state()
        collective["distributed_signals"] = distributed

        for agent in self.agents:
            agent.collective_state = collective
        return step_events

    def collective_state(self) -> dict[str, Any]:
        positions = {
            getattr(agent, "agent_id", f"agent-{idx}"): int(agent.world.agent_position)
            for idx, agent in enumerate(self.agents)
        }
        collective_score = sum(abs(agent.world.goal_position - agent.world.agent_position) for agent in self.agents)
        shared = self.shared_causal_graph.snapshot()
        return {
            "agent_positions": positions,
            "collective_progress_score": -float(collective_score),
            "shared_causal": shared,
            "recent_signals": [
                {"type": s.signal_type, "payload": dict(s.payload), "t": s.t}
                for s in self.collective_signal_bus.get_recent(clear=False)[-20:]
            ],
        }
