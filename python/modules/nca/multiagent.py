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
    collectiveagencylevel: float = 0.0
    collectiveidentityintegrity: float = 1.0
    collective_initiative: dict[str, Any] = field(default_factory=dict)

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

        meta_feedback_map = {
            getattr(agent, "agent_id", f"agent-{idx}"): dict(getattr(agent.metacognition, "latest_feedback", {}))
            for idx, agent in enumerate(self.agents)
        }
        collective["meta_feedback"] = meta_feedback_map

        if collective.get("collectivemetadrift", 0.0) >= 0.4:
            self.collective_signal_bus.emit_broadcast(
                InternalSignal(
                    signal_type="collectivemetadrift",
                    payload={"collectivemetadrift": collective.get("collectivemetadrift", 0.0)},
                )
            )

        if collective.get("collectivemetastabilization"):
            self.collective_signal_bus.emit_broadcast(
                InternalSignal(
                    signal_type="collectivemetastabilization",
                    payload={"collectivemetaalignment": collective.get("collectivemetaalignment", 1.0)},
                )
            )

        if collective.get("collectiveagencyshift"):
            self.collective_signal_bus.emit_broadcast(
                InternalSignal(
                    signal_type="collectiveagencyshift",
                    payload={"collectiveagencylevel": collective.get("collectiveagencylevel", 0.0)},
                )
            )

        if collective.get("collectiveidentityintegritydrop"):
            self.collective_signal_bus.emit_broadcast(
                InternalSignal(
                    signal_type="collectiveidentityintegritydrop",
                    payload={"collectiveidentityintegrity": collective.get("collectiveidentityintegrity", 1.0)},
                )
            )

        if collective.get("collectiveidentityshift"):
            self.collective_signal_bus.emit_broadcast(
                InternalSignal(
                    signal_type="collectiveidentityshift",
                    payload={"collective_self_alignment": collective.get("collective_self_alignment", 1.0)},
                )
            )

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

        self_models = {
            getattr(agent, "agent_id", f"agent-{idx}"): agent.self_model.to_dict()
            for idx, agent in enumerate(self.agents)
        }
        drift_values = [float(model.get("identity_drift_score", 0.0)) for model in self_models.values()]
        collective_self_alignment = max(0.0, min(1.0, 1.0 - (sum(drift_values) / max(1, len(drift_values)))))
        collective_identity_shift = any(drift >= 0.5 for drift in drift_values)

        meta_drifts = [float(model.get("meta_drift_score", 0.0)) for model in self_models.values()]
        collective_meta_drift = sum(meta_drifts) / max(1, len(meta_drifts))
        collective_meta_alignment = max(0.0, min(1.0, 1.0 - collective_meta_drift))
        collective_meta_stabilization = collective_meta_alignment >= 0.65

        identity_cores = {
            getattr(agent, "agent_id", f"agent-{idx}"): {
                "agency_level": float(getattr(agent.identitycore, "agency_level", 0.0)),
                "identity_integrity": float(getattr(agent.identitycore, "identity_integrity", 1.0)),
            }
            for idx, agent in enumerate(self.agents)
        }
        agency_values = [item["agency_level"] for item in identity_cores.values()]
        integrity_values = [item["identity_integrity"] for item in identity_cores.values()]
        self.collectiveagencylevel = sum(agency_values) / max(1, len(agency_values))
        self.collectiveidentityintegrity = sum(integrity_values) / max(1, len(integrity_values))
        self.collective_initiative = {
            "mode": "explore" if self.collectiveagencylevel > 0.6 else "stabilize" if self.collectiveidentityintegrity < 0.55 else "balanced",
            "priority": "identity" if self.collectiveidentityintegrity < 0.6 else "progress",
        }

        return {
            "agent_positions": positions,
            "collective_progress_score": -float(collective_score),
            "shared_causal": shared,
            "self_models": self_models,
            "collective_self_alignment": collective_self_alignment,
            "collectiveidentityshift": collective_identity_shift,
            "collectivemetadrift": collective_meta_drift,
            "collectivemetaalignment": collective_meta_alignment,
            "collectivemetastabilization": collective_meta_stabilization,
            "collectiveagencylevel": self.collectiveagencylevel,
            "collectiveidentityintegrity": self.collectiveidentityintegrity,
            "collective_initiative": dict(self.collective_initiative),
            "collectiveagencyshift": self.collectiveagencylevel > 0.65,
            "collectiveidentityintegritydrop": self.collectiveidentityintegrity < 0.55,
            "recent_signals": [
                {"type": s.signal_type, "payload": dict(s.payload), "t": s.t}
                for s in self.collective_signal_bus.get_recent(clear=False)[-20:]
            ],
        }
