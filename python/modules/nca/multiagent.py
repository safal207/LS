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
    collectiveculturemap: dict[str, dict[str, Any]] = field(default_factory=dict)
    collectivenorms: dict[str, float] = field(default_factory=dict)
    collectivetraditionpatterns: list[dict[str, Any]] = field(default_factory=list)
    civilizationmaturityscore: float = 0.0
    culturalconflictscore: float = 0.0

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
        collective["recent_events"] = [{"agent_id": e.get("agent_id"), "action": e.get("action"), "score": e.get("score", 0.0)} for e in step_events[-len(self.agents):]]

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

        if collective.get("collectiveintentshift"):
            self.collective_signal_bus.emit_broadcast(
                InternalSignal(
                    signal_type="collectiveintentshift",
                    payload={"collectiveintentalignment": collective.get("collectiveintentalignment", 1.0)},
                )
            )

        if collective.get("collectiveintentconflict"):
            self.collective_signal_bus.emit_broadcast(
                InternalSignal(
                    signal_type="collectiveintentconflict",
                    payload={"collectiveintentconflict": collective.get("collectiveintentconflict", 0.0)},
                )
            )

        if collective.get("collectiveautonomyshift"):
            self.collective_signal_bus.emit_broadcast(
                InternalSignal(
                    signal_type="collectiveautonomyshift",
                    payload={"collectiveautonomylevel": collective.get("collectiveautonomylevel", 0.0)},
                )
            )

        if collective.get("collectivevalueshift"):
            self.collective_signal_bus.emit_broadcast(
                InternalSignal(
                    signal_type="collectivevalueshift",
                    payload={"collectivevaluealignment": collective.get("collectivevaluealignment", 1.0)},
                )
            )

        if collective.get("collectiveethicalconflict") > 0.35:
            self.collective_signal_bus.emit_broadcast(
                InternalSignal(
                    signal_type="collectiveethicalconflict",
                    payload={"collectiveethicalconflict": collective.get("collectiveethicalconflict", 0.0)},
                )
            )

        if collective.get("collectiveautonomyconflict") > 0.35:
            self.collective_signal_bus.emit_broadcast(
                InternalSignal(
                    signal_type="collectiveautonomyconflict",
                    payload={"collectiveautonomyconflict": collective.get("collectiveautonomyconflict", 0.0)},
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

        intent_map = {
            getattr(agent, "agent_id", f"agent-{idx}"): {
                "primary_intent": dict(getattr(agent.intentengine, "select_primary_intent")() or {}),
                "intent_strength": float(getattr(agent.intentengine, "intent_strength", 0.0)),
                "intent_alignment": float(getattr(agent.intentengine, "intent_alignment", 1.0)),
                "conflicts": list(getattr(agent.intentengine, "intent_conflicts", [])),
            }
            for idx, agent in enumerate(self.agents)
        }
        self.collectiveintentmap = intent_map
        alignment_values = [float(v.get("intent_alignment", 1.0)) for v in intent_map.values()]
        conflict_values = [min(1.0, len(v.get("conflicts", [])) / 3.0) for v in intent_map.values()]
        self.collectiveintentalignment = sum(alignment_values) / max(1, len(alignment_values))
        self.collectiveintentconflict = sum(conflict_values) / max(1, len(conflict_values))

        autonomy_map = {
            getattr(agent, "agent_id", f"agent-{idx}"): {
                "autonomy_level": float(getattr(agent.autonomy, "autonomy_level", 0.0)),
                "primary_strategy": dict(getattr(agent.autonomy, "select_strategy")() or {}),
                "autonomy_conflicts": list(getattr(agent.autonomy, "autonomy_conflicts", [])),
            }
            for idx, agent in enumerate(self.agents)
        }
        self.collectivestrategymap = autonomy_map
        autonomy_levels = [float(v.get("autonomy_level", 0.0)) for v in autonomy_map.values()]
        autonomy_conflicts = [min(1.0, len(v.get("autonomy_conflicts", [])) / 3.0) for v in autonomy_map.values()]
        self.collectiveautonomylevel = sum(autonomy_levels) / max(1, len(autonomy_levels))
        self.collectiveautonomyconflict = sum(autonomy_conflicts) / max(1, len(autonomy_conflicts))


        value_map = {
            getattr(agent, "agent_id", f"agent-{idx}"): {
                "core_values": dict(getattr(agent.values, "core_values", {})),
                "valuealignmentscore": float(getattr(agent.values, "valuealignmentscore", 1.0)),
                "ethical_constraints": dict(getattr(agent.values, "ethical_constraints", {})),
                "preference_drift": float(getattr(agent.values, "preference_drift", 0.0)),
                "value_conflicts": list(getattr(agent.values, "value_conflicts", [])),
            }
            for idx, agent in enumerate(self.agents)
        }
        self.collectivevaluemap = value_map
        value_alignments = [float(v.get("valuealignmentscore", 1.0)) for v in value_map.values()]
        value_conflicts = [min(1.0, len(v.get("value_conflicts", [])) / 3.0) for v in value_map.values()]
        self.collectivevaluealignment = sum(value_alignments) / max(1, len(value_alignments))
        self.collectiveethicalconflict = sum(value_conflicts) / max(1, len(value_conflicts))

        culture_map = {
            getattr(agent, "agent_id", f"agent-{idx}"): {
                "culturalalignmentscore": float(getattr(agent.culture, "culturalalignmentscore", 0.5)),
                "norms": dict(getattr(agent.culture, "norms", {})),
                "norm_conflicts": list(getattr(agent.culture, "norm_conflicts", [])),
                "traditions": [dict(t) for t in list(getattr(agent.culture, "traditions", []))[-5:]],
            }
            for idx, agent in enumerate(self.agents)
        }
        self.collectiveculturemap = culture_map
        culture_alignments = [float(v.get("culturalalignmentscore", 0.5)) for v in culture_map.values()]
        conflict_levels = [min(1.0, len(v.get("norm_conflicts", [])) / 4.0) for v in culture_map.values()]
        self.culturalconflictscore = sum(conflict_levels) / max(1, len(conflict_levels)) if conflict_levels else 0.0

        norm_accum: dict[str, float] = {}
        norm_count: dict[str, int] = {}
        for item in culture_map.values():
            for key, val in dict(item.get("norms", {})).items():
                norm_accum[key] = norm_accum.get(key, 0.0) + float(val)
                norm_count[key] = norm_count.get(key, 0) + 1
        self.collectivenorms = {k: norm_accum[k] / max(1, norm_count[k]) for k in norm_accum}

        tradition_bag: list[dict[str, Any]] = []
        for item in culture_map.values():
            tradition_bag.extend([dict(t) for t in item.get("traditions", [])])
        self.collectivetraditionpatterns = tradition_bag[-20:]

        collective_culture_alignment = sum(culture_alignments) / max(1, len(culture_alignments)) if culture_alignments else 0.0
        self.civilizationmaturityscore = max(0.0, min(1.0, collective_culture_alignment - (0.35 * self.culturalconflictscore)))

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
            "collectiveintentmap": dict(self.collectiveintentmap),
            "collectiveintentalignment": self.collectiveintentalignment,
            "collectiveintentconflict": self.collectiveintentconflict,
            "collectiveautonomylevel": self.collectiveautonomylevel,
            "collectivestrategymap": dict(self.collectivestrategymap),
            "collectiveautonomyconflict": self.collectiveautonomyconflict,
            "collectivevaluemap": dict(self.collectivevaluemap),
            "collectivevaluealignment": self.collectivevaluealignment,
            "collectiveethicalconflict": self.collectiveethicalconflict,
            "collectiveculturemap": dict(self.collectiveculturemap),
            "collectivenorms": dict(self.collectivenorms),
            "collectivetraditionpatterns": [dict(t) for t in self.collectivetraditionpatterns],
            "collectiveculturealignment": collective_culture_alignment,
            "civilizationmaturityscore": self.civilizationmaturityscore,
            "culturalconflictscore": self.culturalconflictscore,
            "collectiveidentityintegrity": self.collectiveidentityintegrity,
            "collective_initiative": dict(self.collective_initiative),
            "collectiveagencyshift": self.collectiveagencylevel > 0.65,
            "collectiveintentshift": self.collectiveintentalignment < 0.6,
            "collectiveautonomyshift": self.collectiveautonomylevel > 0.62,
            "collectiveidentityintegritydrop": self.collectiveidentityintegrity < 0.55,
            "collectivevalueshift": self.collectivevaluealignment < 0.62,
            "collectivecultureshift": collective_culture_alignment < 0.6,
            "collectivenormformation": len(self.collectivenorms) >= 3,
            "collectivecivilizationevent": self.civilizationmaturityscore > 0.68 or self.culturalconflictscore > 0.45,
            "recent_signals": [
                {"type": s.signal_type, "payload": dict(s.payload), "t": s.t}
                for s in self.collective_signal_bus.get_recent(clear=False)[-20:]
            ],
        }
