from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .assembly import AgentState, AssemblyPoint
from .autonomy_engine import AutonomyEngine
from .causal import CausalGraph
from .culture_engine import CultureEngine
from .meta_observer import MetaObserver
from .meta_cognition import MetaCognitionEngine
from .identity_core import IdentityCore
from .intent_engine import IntentEngine
from .orientation import OrientationCenter
from .self_model import SelfModel
from .social_cognition import SocialCognitionEngine
from .signals import InternalSignal, SignalBus
from .trajectories import TrajectoryPlanner
from .value_system import ValueSystem
from .world import GridWorld


@dataclass
class NCAAgent:
    """Composes NCA Phase 1 components into a runnable agent loop."""

    world: GridWorld
    orientation: OrientationCenter
    assembly: AssemblyPoint = field(default_factory=AssemblyPoint)
    meta_observer: MetaObserver = field(default_factory=MetaObserver)
    planner: TrajectoryPlanner = field(default_factory=TrajectoryPlanner)
    causal_graph: CausalGraph = field(default_factory=CausalGraph)
    signal_bus: SignalBus = field(default_factory=SignalBus)
    signal_log: list[dict[str, Any]] = field(default_factory=list)
    low_confidence_threshold: float = 0.35
    collective_state: dict[str, Any] = field(default_factory=dict)
    self_model: SelfModel = field(default_factory=SelfModel)
    metacognition: MetaCognitionEngine = field(default_factory=MetaCognitionEngine)
    identitycore: IdentityCore = field(default_factory=IdentityCore)
    intentengine: IntentEngine = field(default_factory=IntentEngine)
    autonomy: AutonomyEngine = field(default_factory=AutonomyEngine)
    values: ValueSystem = field(default_factory=ValueSystem)
    social: SocialCognitionEngine = field(default_factory=SocialCognitionEngine)
    culture: CultureEngine = field(default_factory=CultureEngine)

    def __post_init__(self) -> None:
        self.planner.causal_graph = self.causal_graph
        self.signal_bus.subscribe(self._log_signal)
        self.signal_bus.subscribe(self._orientation_signal_handler)

    def _log_signal(self, signal: InternalSignal) -> None:
        self.signal_log.append(
            {
                "t": signal.t,
                "type": signal.signal_type,
                "payload": dict(signal.payload),
                "timestamp": signal.timestamp,
            }
        )

    def _orientation_signal_handler(self, signal: InternalSignal) -> None:
        if signal.signal_type == "orientationfeedbackrequired":
            self.orientation.update_from_feedback(
                {
                    "preference_updates": {"stability": 0.05},
                }
            )
        if signal.signal_type == "causal_drift":
            self.orientation.update_from_feedback(
                {
                    "preference_updates": {"stability": 0.08},
                }
            )
            self.orientation.stability_preference = min(1.0, self.orientation.stability_preference + 0.05)
            self.orientation.impulsiveness = max(0.0, self.orientation.impulsiveness - 0.05)
        if signal.signal_type in ("multiagent_drift", "coordination_required"):
            feedback_signal = self.orientation.update_from_collective_feedback(
                {
                    "collective_drift": signal.signal_type == "multiagent_drift",
                    "collective_progress": float(signal.payload.get("collective_score", 0.0)),
                    "goal_conflict": signal.signal_type == "coordination_required",
                }
            )
            if feedback_signal:
                self.signal_bus.emit(
                    InternalSignal(
                        signal_type=feedback_signal["signal_type"],
                        t=signal.t,
                        payload=feedback_signal["payload"],
                    )
                )

    def build_state(self) -> AgentState:
        return self.assembly.build(
            t=self.world.t,
            world_state=self.world.state(),
            orientation=self.orientation,
            signal_bus=self.signal_bus,
        )

    def step(self) -> dict[str, Any]:
        """Execute one decision cycle and return structured step output."""
        state = self.build_state()

        self_snapshot = self.self_model.update_from_state(state)
        analysis = self.meta_observer.observe_and_correct(state, self.orientation, self.signal_bus, self_model=self.self_model)
        self.orientation.update_from_self_model(self.self_model)

        metafeedback = self.metacognition.analyze_cognition(state, self.self_model, analysis["report"])

        self.identitycore.update_from_self_model(self.self_model)
        self.identitycore.update_from_meta(metafeedback)
        self.identitycore.stabilize_identity()
        initiative = self.identitycore.generate_initiative()

        self.values.update_from_identity(self.identitycore)

        self.social.update_from_identity(self.identitycore)
        self.social.update_from_values(self.values)
        self.social.update_from_collective(self.collective_state)

        self.culture.updatefromsocial(self.social)
        self.culture.updatefromvalues(self.values)
        self.culture.updatefromcollective(self.collective_state)
        collectiveevents = list(self.collective_state.get("recent_events", [])) if isinstance(self.collective_state, dict) else []
        self.culture.infernorms(collectiveevents)
        self.culture.evolve_norms()
        culturalalignment = self.culture.evaluate_cultural_alignment(self)
        civilizationadjustments = self.culture.generate_civilization_adjustments()
        self.identitycore.evaluate_cultural_compatibility(self.culture)

        strategies = self.autonomy.generate_strategies(
            self.identitycore,
            self.intentengine,
            self.metacognition,
            values=self.values,
            civilization_adjustments=civilizationadjustments,
        )
        primary_strategy = self.autonomy.select_strategy()

        intents = self.intentengine.generate_intents(
            state,
            self.identitycore,
            self.self_model,
            strategy=primary_strategy,
            values=self.values,
            culture=self.culture,
        )
        primary_intent = self.intentengine.select_primary_intent()

        self.values.update_from_intents(self.intentengine)
        self.values.update_from_autonomy(self.autonomy)

        preferred_actions = list((initiative or {}).get("preferred_actions", []))
        if not preferred_actions and isinstance(primary_intent, dict):
            preferred_actions = list(primary_intent.get("preferred_actions", []))
        value_action = {"action": preferred_actions[0] if preferred_actions else "idle"}
        valuealignment = self.values.evaluate_value_alignment(value_action, primary_intent, primary_strategy)

        self.values.evolve_preferences()
        self.identitycore.evaluate_value_compatibility(self.values)

        candidates = self.planner.generate(
            self.world,
            state,
            initiative=initiative,
            intent=primary_intent,
            strategy=primary_strategy,
            values=self.values,
            social=self.social,
            culture=self.culture,
        )
        evaluated = self.planner.evaluate(
            candidates,
            state,
            collective_state=self.collective_state,
            self_model=self.self_model,
            metafeedback=metafeedback,
            initiative=initiative,
            intent=primary_intent,
            strategy=primary_strategy,
            values=self.values,
            social=self.social,
            culture=self.culture,
        )
        choice = self.planner.choose(evaluated)

        self.orientation.update_from_identity_core(self.identitycore)
        self.self_model.update_identity_metrics(self.identitycore)
        self.self_model.update_intent_metrics(self.intentengine)
        self.autonomy.update_autonomy_metrics()
        self.self_model.update_autonomy_metrics(self.autonomy)
        self.self_model.update_value_metrics(self.values)
        self.self_model.update_culture_metrics(self.culture)

        self.self_model.update_cognitive_trace(
            state,
            {"action": choice.action, "score": choice.score, "confidence": choice.confidence},
            {**analysis, "meta_drift": metafeedback.get("meta_drift", 0.0)},
        )
        self.metacognition.apply_corrections(self)

        if choice.confidence < self.low_confidence_threshold:
            self.signal_bus.emit(
                InternalSignal(
                    signal_type="low_confidence",
                    t=state.t,
                    payload={"confidence": choice.confidence, "action": choice.action},
                )
            )

        state_before = state.world_state if isinstance(state.world_state, dict) else {}
        transition = self.world.step(choice.action)
        state_after = self.world.state()
        self.causal_graph.record_transition(state_before, choice.action, state_after)

        event = {
            "t": transition["t"],
            "action": choice.action,
            "score": choice.score,
            "details": dict(choice.details),
            "analysis": analysis,
            "confidence": choice.confidence,
            "uncertainty": choice.uncertainty,
            "causal_score": choice.causal_score,
            "causal_graph": self.causal_graph.to_dict(),
            "self_model": self.self_model.to_dict(),
            "self_model_snapshot": self_snapshot,
            "metacognition": metafeedback,
            "initiative": initiative,
            "intents": intents,
            "primary_intent": primary_intent,
            "strategies": strategies,
            "primary_strategy": primary_strategy,
            "value_alignment": valuealignment,
            "cultural_alignment": culturalalignment,
            "civilization_adjustments": civilizationadjustments,
            "social": {
                "group_norms": dict(self.social.group_norms),
                "tradition_patterns": [dict(p) for p in self.social.tradition_patterns[-20:]],
                "culturalsimilarityscore": self.social.culturalsimilarityscore,
                "collaboration_index": self.social.collaboration_index,
                "conflict_index": self.social.conflict_index,
            },
            "culture": {
                "norms": dict(self.culture.norms),
                "culturalalignmentscore": self.culture.culturalalignmentscore,
                "norm_conflicts": [dict(c) for c in self.culture.norm_conflicts],
                "traditions": [dict(t) for t in self.culture.traditions[-20:]],
                "civilization_state": dict(self.culture.civilization_state),
                "culture_trace": list(self.culture.culture_trace[-20:]),
            },
            "values": {
                "core_values": dict(self.values.core_values),
                "valuealignmentscore": self.values.valuealignmentscore,
                "ethical_constraints": dict(self.values.ethical_constraints),
                "preference_drift": self.values.preference_drift,
                "value_conflicts": [dict(c) for c in self.values.value_conflicts],
                "value_trace": list(self.values.value_trace[-20:]),
                "culturalvaluealignment": self.values.culturalvaluealignment,
                "normethicsmap": dict(self.values.normethicsmap),
                "traditionvaluemap": dict(self.values.traditionvaluemap),
            },
            "autonomy": {
                "autonomy_level": self.autonomy.autonomy_level,
                "strategy_profile": dict(self.autonomy.strategy_profile),
                "selfdirectedgoals": [dict(g) for g in self.autonomy.selfdirectedgoals],
                "autonomy_conflicts": [dict(c) for c in self.autonomy.autonomy_conflicts],
                "autonomy_trace": list(self.autonomy.autonomy_trace[-20:]),
                "ethicalalignmentscore": self.autonomy.ethicalalignmentscore,
                "selfregulationstrength": self.autonomy.selfregulationstrength,
                "civilizationalignmentscore": self.autonomy.civilizationalignmentscore,
                "normcompliancefactor": self.autonomy.normcompliancefactor,
                "culturalstrategyadjustment": self.autonomy.culturalstrategyadjustment,
            },
            "identity_core": {
                "core_traits": dict(self.identitycore.core_traits),
                "longtermgoals": list(self.identitycore.longtermgoals),
                "identity_integrity": self.identitycore.identity_integrity,
                "drift_resistance": self.identitycore.drift_resistance,
                "agency_level": self.identitycore.agency_level,
                "intentalignmentscore": self.identitycore.intentalignmentscore,
                "intent_resistance": self.identitycore.intent_resistance,
                "autonomyalignmentscore": self.identitycore.autonomyalignmentscore,
                "autonomy_resistance": self.identitycore.autonomy_resistance,
                "selfdirectionpreference": dict(self.identitycore.selfdirectionpreference),
                "valuealignmentscore": self.identitycore.valuealignmentscore,
                "value_resistance": self.identitycore.value_resistance,
                "valuepreferenceprofile": dict(self.identitycore.valuepreferenceprofile),
                "culturalidentityscore": self.identitycore.culturalidentityscore,
                "cultural_resistance": self.identitycore.cultural_resistance,
                "culturalpreferenceprofile": dict(self.identitycore.culturalpreferenceprofile),
            },
            "signals": [
                {"type": s.signal_type, "payload": s.payload}
                for s in self.signal_bus.get_recent(clear=True)
            ],
            **transition,
        }
        self.assembly.append_history(event)
        self.assembly.prune_history()
        return event
