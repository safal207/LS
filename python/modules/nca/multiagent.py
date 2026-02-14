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
    collectiveintentmap: dict[str, dict[str, Any]] = field(default_factory=dict)
    collectiveintentalignment: float = 1.0
    collectiveintentconflict: float = 0.0
    collectiveautonomylevel: float = 0.0
    collectivestrategymap: dict[str, dict[str, Any]] = field(default_factory=dict)
    collectiveautonomyconflict: float = 0.0
    collectivevaluemap: dict[str, dict[str, Any]] = field(default_factory=dict)
    collectivevaluealignment: float = 1.0
    collectiveethicalconflict: float = 0.0
    collectivesocialmap: dict[str, dict[str, Any]] = field(default_factory=dict)
    collectivecooperationscore: float = 0.0
    collectiveethicalalignment: float = 1.0
    collectivesocialconflict: float = 0.0

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
        collective["recent_events"] = [dict(e) for e in step_events[-20:]]
        collective["distributed_signals"] = distributed

        if collective.get("collectivesocialshift"):
            self.collective_signal_bus.emit_broadcast(InternalSignal(signal_type="collectivesocialshift", payload={"collectivecooperationscore": collective.get("collectivecooperationscore", 0.0)}))
        if collective.get("collectivecooperation"):
            self.collective_signal_bus.emit_broadcast(InternalSignal(signal_type="collectivecooperation", payload={"collectivecooperationscore": collective.get("collectivecooperationscore", 0.0)}))
        if collective.get("collectivesocialconflict", 0.0) > 0.35:
            self.collective_signal_bus.emit_broadcast(InternalSignal(signal_type="collectivesocialconflict", payload={"collectivesocialconflict": collective.get("collectivesocialconflict", 0.0)}))

        for agent in self.agents:
            agent.collective_state = collective
        return step_events

    def collective_state(self) -> dict[str, Any]:
        positions = {getattr(agent, "agent_id", f"agent-{idx}"): int(agent.world.agent_position) for idx, agent in enumerate(self.agents)}
        collective_score = sum(abs(agent.world.goal_position - agent.world.agent_position) for agent in self.agents)
        shared = self.shared_causal_graph.snapshot()

        self.collectiveintentmap = {
            getattr(agent, "agent_id", f"agent-{idx}"): {
                "primary_intent": dict(getattr(agent.intentengine, "select_primary_intent")() or {}),
                "intent_alignment": float(getattr(agent.intentengine, "intent_alignment", 1.0)),
                "conflicts": list(getattr(agent.intentengine, "intent_conflicts", [])),
            }
            for idx, agent in enumerate(self.agents)
        }
        ia = [float(v.get("intent_alignment", 1.0)) for v in self.collectiveintentmap.values()]
        ic = [min(1.0, len(v.get("conflicts", [])) / 3.0) for v in self.collectiveintentmap.values()]
        self.collectiveintentalignment = sum(ia) / max(1, len(ia))
        self.collectiveintentconflict = sum(ic) / max(1, len(ic))

        self.collectivestrategymap = {
            getattr(agent, "agent_id", f"agent-{idx}"): {
                "autonomy_level": float(getattr(agent.autonomy, "autonomy_level", 0.0)),
                "primary_strategy": dict(getattr(agent.autonomy, "select_strategy")() or {}),
                "autonomy_conflicts": list(getattr(agent.autonomy, "autonomy_conflicts", [])),
            }
            for idx, agent in enumerate(self.agents)
        }
        al = [float(v.get("autonomy_level", 0.0)) for v in self.collectivestrategymap.values()]
        ac = [min(1.0, len(v.get("autonomy_conflicts", [])) / 3.0) for v in self.collectivestrategymap.values()]
        self.collectiveautonomylevel = sum(al) / max(1, len(al))
        self.collectiveautonomyconflict = sum(ac) / max(1, len(ac))

        self.collectivevaluemap = {
            getattr(agent, "agent_id", f"agent-{idx}"): {
                "core_values": dict(getattr(agent.values, "core_values", {})),
                "valuealignmentscore": float(getattr(agent.values, "valuealignmentscore", 1.0)),
                "value_conflicts": list(getattr(agent.values, "value_conflicts", [])),
            }
            for idx, agent in enumerate(self.agents)
        }
        va = [float(v.get("valuealignmentscore", 1.0)) for v in self.collectivevaluemap.values()]
        vc = [min(1.0, len(v.get("value_conflicts", [])) / 3.0) for v in self.collectivevaluemap.values()]
        self.collectivevaluealignment = sum(va) / max(1, len(va))
        self.collectiveethicalconflict = sum(vc) / max(1, len(vc))

        self.collectivesocialmap = {
            getattr(agent, "agent_id", f"agent-{idx}"): {
                "cooperation_score": float(getattr(agent.social, "cooperation_score", 0.0)),
                "socialconflictscore": float(getattr(agent.social, "socialconflictscore", 0.0)),
                "collectivevaluealignment": float(getattr(agent.social, "collectivevaluealignment", 1.0)),
                "collectiveintentalignment": float(getattr(agent.social, "collectiveintentalignment", 1.0)),
            }
            for idx, agent in enumerate(self.agents)
        }
        cs = [float(v.get("cooperation_score", 0.0)) for v in self.collectivesocialmap.values()]
        sc = [float(v.get("socialconflictscore", 0.0)) for v in self.collectivesocialmap.values()]
        self.collectivecooperationscore = sum(cs) / max(1, len(cs))
        self.collectivesocialconflict = sum(sc) / max(1, len(sc))
        self.collectiveethicalalignment = max(0.0, min(1.0, (0.6 * self.collectivevaluealignment) + (0.4 * (1.0 - self.collectiveethicalconflict))))

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

        return {
            "agent_positions": positions,
            "collective_progress_score": -float(collective_score),
            "shared_causal": shared,
            "collectiveagencylevel": self.collectiveagencylevel,
            "collectiveintentmap": dict(self.collectiveintentmap),
            "collectiveintentalignment": self.collectiveintentalignment,
            "collectiveintentconflict": self.collectiveintentconflict,
            "collectiveautonomylevel": self.collectiveautonomylevel,
            "collectivestrategymap": dict(self.collectivestrategymap),
            "collectiveautonomyconflict": self.collectiveautonomyconflict,
            "collectivevaluemap": dict(self.collectivevaluemap),
            "collectivevaluealignment": self.collectivevaluealignment,
            "collectiveethicalconflict": self.collectiveethicalconflict,
            "collectivesocialmap": dict(self.collectivesocialmap),
            "collectivecooperationscore": self.collectivecooperationscore,
            "collectiveethicalalignment": self.collectiveethicalalignment,
            "collectivesocialconflict": self.collectivesocialconflict,
            "collectiveidentityintegrity": self.collectiveidentityintegrity,
            "collectiveagencyshift": self.collectiveagencylevel > 0.65,
            "collectiveintentshift": self.collectiveintentalignment < 0.6,
            "collectiveautonomyshift": self.collectiveautonomylevel > 0.62,
            "collectiveidentityintegritydrop": self.collectiveidentityintegrity < 0.55,
            "collectivevalueshift": self.collectivevaluealignment < 0.62,
            "collectivesocialshift": self.collectivecooperationscore < 0.55,
            "collectivecooperation": self.collectivecooperationscore > 0.65,
            "recent_signals": [
                {"type": s.signal_type, "payload": dict(s.payload), "t": s.t}
                for s in self.collective_signal_bus.get_recent(clear=False)[-20:]
            ],
        }
