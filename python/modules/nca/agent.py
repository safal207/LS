from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .assembly import AgentState, AssemblyPoint
from .autonomy_engine import AutonomyEngine
from .causal import CausalGraph
from .culture_engine import CultureEngine
from .identity_core import IdentityCore
from .intent_engine import IntentEngine
from .meta_cognition import MetaCognitionEngine
from .meta_observer import MetaObserver
from .orientation import OrientationCenter
from .self_model import SelfModel
from .signals import InternalSignal, SignalBus
from .social_cognition import SocialCognitionEngine
from .trajectories import TrajectoryPlanner
from .value_system import ValueSystem
from .world import GridWorld


@dataclass
class NCAAgent:
    """Composable NCA agent with identity, social, and cultural layers."""

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
    autonomy: AutonomyEngine = field(default_factory=AutonomyEngine)
    values: ValueSystem = field(default_factory=ValueSystem)
    social: SocialCognitionEngine = field(default_factory=SocialCognitionEngine)
    culture: CultureEngine = field(default_factory=CultureEngine)
    intentengine: IntentEngine = field(default_factory=IntentEngine)

    def __post_init__(self) -> None:
        self.planner.causal_graph = self.causal_graph
        self.signal_bus.subscribe(self._log_signal)
        self.signal_bus.subscribe(self._orientation_signal_handler)

    def _log_signal(self, signal: InternalSignal) -> None:
        self.signal_log.append({"t": signal.t, "type": signal.signal_type, "payload": dict(signal.payload), "timestamp": signal.timestamp})

    def _orientation_signal_handler(self, signal: InternalSignal) -> None:
        if signal.signal_type in ("orientationfeedbackrequired", "causal_drift"):
            self.orientation.update_from_feedback({"preference_updates": {"stability": 0.05}})

    def build_state(self) -> AgentState:
        return self.assembly.build(t=self.world.t, world_state=self.world.state(), orientation=self.orientation, signal_bus=self.signal_bus)

    def step(self) -> dict[str, Any]:
        state = self.build_state()
        self_snapshot = self.self_model.update_from_state(state)
        analysis = self.meta_observer.observe_and_correct(state, self.orientation, self.signal_bus, self_model=self.self_model)
        self.orientation.update_from_self_model(self.self_model)

        metafeedback = self.metacognition.analyze_cognition(state, self.self_model, analysis["report"])

        # 1) identity
        self.identitycore.update_from_self_model(self.self_model)
        self.identitycore.update_from_meta(metafeedback)
        self.identitycore.stabilize_identity()
        initiative = self.identitycore.generate_initiative()

        # 2) metacognition already computed above
        # 3) values
        self.values.update_from_identity(self.identitycore)
        self.values.update_from_collective(self.collective_state)

        # 4) social cognition
        self.social.update_from_collective_state(self.collective_state)
        collective_events = list(self.collective_state.get("recent_events", [])) if isinstance(self.collective_state, dict) else []
        self.social.infer_other_agents_intents(collective_events)
        self.social.infer_other_agents_values(collective_events)
        socialalignment = self.social.evaluate_social_alignment(self, self.collective_state)
        cooperativeadjustments = self.social.generate_cooperative_adjustments()
        self.identitycore.evaluate_social_compatibility(self.social)

        # 5) culture engine
        self.culture.update_from_social(self.social)
        self.culture.update_from_values(self.values)
        self.culture.update_from_collective(self.collective_state)
        self.culture.infer_norms(collective_events)
        self.culture.evolve_norms()
        cultural_alignment = self.culture.evaluate_cultural_alignment(self)
        civilization_adjustments = self.culture.generate_civilization_adjustments()
        self.identitycore.evaluate_cultural_compatibility(self.culture)

        # 6) autonomy
        strategies = self.autonomy.generate_strategies(self.identitycore, self.intentengine, self.metacognition, values=self.values, culture=self.culture)
        self.autonomy.apply_cooperative_regulation(self.social, self.collective_state)
        primary_strategy = self.autonomy.select_strategy()

        # 7) intent engine
        intents = self.intentengine.generate_intents(
            state,
            self.identitycore,
            self.self_model,
            strategy=primary_strategy,
            values=self.values,
            social=self.social,
            collective_state=self.collective_state,
        )
        primary_intent = self.intentengine.select_primary_intent()
        self.values.update_from_intents(self.intentengine)
        self.values.update_from_autonomy(self.autonomy)
        valuealignment = self.values.evaluate_value_alignment({"action": "forward"}, primary_intent, primary_strategy)
        self.values.evolve_preferences()
        self.identitycore.evaluate_value_compatibility(self.values)

        # 8) planner
        candidates = self.planner.generate(self.world, state, initiative=initiative, intent=primary_intent, strategy=primary_strategy, values=self.values, social=self.social, culture=self.culture)
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
        self.self_model.update_social_metrics(self.social)
        self.self_model.update_culture_metrics(self.culture)
        self.self_model.update_cognitive_trace(state, {"action": choice.action, "score": choice.score, "confidence": choice.confidence}, {**analysis, "meta_drift": metafeedback.get("meta_drift", 0.0)})
        self.metacognition.apply_corrections(self)

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
            "social_alignment": socialalignment,
            "cooperative_adjustments": cooperativeadjustments,
            "cultural_alignment": cultural_alignment,
            "civilization_adjustments": civilization_adjustments,
            "social_prediction": self.social.predict_group_behavior(),
            "values": {
                "core_values": dict(self.values.core_values),
                "valuealignmentscore": self.values.valuealignmentscore,
                "ethical_constraints": dict(self.values.ethical_constraints),
                "preference_drift": self.values.preference_drift,
                "value_conflicts": [dict(c) for c in self.values.value_conflicts],
                "collectivevaluealignment": self.values.collectivevaluealignment,
            },
            "autonomy": {
                "autonomy_level": self.autonomy.autonomy_level,
                "strategy_profile": dict(self.autonomy.strategy_profile),
                "civilizationalignmentscore": self.autonomy.civilizationalignmentscore,
                "normcompliancefactor": self.autonomy.normcompliancefactor,
                "culturalstrategyadjustment": dict(self.autonomy.culturalstrategyadjustment),
            },
            "identity_core": {
                "identity_integrity": self.identitycore.identity_integrity,
                "agency_level": self.identitycore.agency_level,
                "socialalignmentscore": self.identitycore.socialalignmentscore,
                "culturalidentityscore": self.identitycore.culturalidentityscore,
            },
            "social": {
                "social_models": dict(self.social.social_models),
                "collectivevaluealignment": self.social.collectivevaluealignment,
                "collectiveintentalignment": self.social.collectiveintentalignment,
                "socialconflictscore": self.social.socialconflictscore,
                "cooperation_score": self.social.cooperation_score,
                "group_norms": dict(self.social.group_norms),
                "tradition_patterns": dict(self.social.tradition_patterns),
                "culturalsimilarityscore": self.social.culturalsimilarityscore,
            },
            "culture": {
                "norms": dict(self.culture.norms),
                "traditions": dict(self.culture.traditions),
                "culture_trace": list(self.culture.culture_trace[-20:]),
                "norm_conflicts": [dict(c) for c in self.culture.norm_conflicts],
                "civilization_state": dict(self.culture.civilization_state),
            },
            "signals": [{"type": s.signal_type, "payload": s.payload} for s in self.signal_bus.get_recent(clear=True)],
            **transition,
        }
        self.assembly.append_history(event)
        self.assembly.prune_history()
        return event
