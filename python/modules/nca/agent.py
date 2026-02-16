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
from .militocracy_engine import MilitocracyEngine
from .orientation import OrientationCenter
from .self_model import SelfModel
from .signals import InternalSignal, SignalBus
from .social_cognition import SocialCognitionEngine
from .synergy_engine import SynergyEngine
from .trajectories import TrajectoryPlanner
from .value_system import ValueSystem
from .world import GridWorld
from .update_context import UpdateContext


@dataclass
class NCAAgent:
    """Composable NCA agent with identity, social, cultural, and phase 11.1 layers."""

    world: GridWorld
    orientation: OrientationCenter
    assembly: AssemblyPoint = field(default_factory=AssemblyPoint)
    # meta_observer and metacognition removed as fields (now in self_model)
    planner: TrajectoryPlanner = field(default_factory=TrajectoryPlanner)
    causal_graph: CausalGraph = field(default_factory=CausalGraph)
    signal_bus: SignalBus = field(default_factory=SignalBus)
    signal_log: list[dict[str, Any]] = field(default_factory=list)
    low_confidence_threshold: float = 0.35
    collective_state: dict[str, Any] = field(default_factory=dict)
    self_model: SelfModel = field(default_factory=SelfModel)
    identitycore: IdentityCore = field(default_factory=IdentityCore)
    autonomy: AutonomyEngine = field(default_factory=AutonomyEngine)
    values: ValueSystem = field(default_factory=ValueSystem)
    social: SocialCognitionEngine = field(default_factory=SocialCognitionEngine)
    culture: CultureEngine = field(default_factory=CultureEngine)
    militocracy: MilitocracyEngine = field(default_factory=MilitocracyEngine)
    synergy: SynergyEngine = field(default_factory=SynergyEngine)
    intentengine: IntentEngine = field(default_factory=IntentEngine)

    @property
    def meta_observer(self) -> MetaObserver:
        return self.self_model.meta_observer

    @property
    def metacognition(self) -> MetaCognitionEngine:
        return self.self_model.metacognition

    def __post_init__(self) -> None:
        self.planner.causal_graph = self.causal_graph
        self.signal_bus.subscribe(self._log_signal)
        # Phase 13: Signal handling for orientation moved to closed-loop update(context)
        # self.signal_bus.subscribe(self._orientation_signal_handler)

        # Inject signal bus into self_model for meta-observer
        self.self_model.signal_bus = self.signal_bus

    def _log_signal(self, signal: InternalSignal) -> None:
        self.signal_log.append(
            {
                "t": signal.t,
                "type": signal.signal_type,
                "payload": dict(signal.payload),
                "timestamp": signal.timestamp,
            }
        )

    def build_state(self) -> AgentState:
        return self.assembly.build(
            t=self.world.t,
            world_state=self.world.state(),
            orientation=self.orientation,
            signal_bus=self.signal_bus,
        )

    def step(self) -> dict[str, Any]:
        """Unified Update Loop (UUL) v1.0 Agent Step"""

        # 1. Input Layer
        state = self.build_state()

        # Phase 12.1: Deterministic Context Propagation
        context = UpdateContext(
            t=state.t,
            state=state,
            collective_state=self.collective_state,
            values_snapshot=self.values.to_context_snapshot(),
            autonomy_snapshot=self.autonomy.to_context_snapshot(),
            intent_snapshot=self.intentengine.to_context_snapshot(),
            primary_intent=None,
            social_snapshot=self.social.to_context_snapshot(),
            culture_snapshot=self.culture.to_context_snapshot(),
            militocracy_snapshot=self.militocracy.to_context_snapshot(),
            synergy_snapshot=self.synergy.to_context_snapshot(),
            identity_snapshot=self.identitycore.to_context_snapshot(),
            # Phase 13: Orientation snapshot
            orientation_snapshot=self.orientation.to_snapshot(),
        )

        # 2. Self-Model Layer (Phase 13: Context-Native Update)
        self_result = self.self_model.update(context)
        context = context.evolve(
            self_snapshot=self_result["snapshot"],
            meta_report=self_result.get("analysis"),
            metafeedback=self_result.get("metafeedback"),
        )
        # Extract analysis/metafeedback for later use in step
        analysis = self_result.get("analysis", {})
        metafeedback = self_result.get("metafeedback", {})
        self_snapshot = self_result["snapshot"]

        # Phase 13: Orientation update via context
        orientation_result = self.orientation.update(context)
        context = context.evolve(
            orientation_snapshot=orientation_result["snapshot"]
        )

        # 3. Identity Layer
        identity_result = self.identitycore.update(context)
        context = context.evolve(
            identity_snapshot=identity_result["snapshot"],
            initiative=identity_result["initiative"]
        )
        initiative = identity_result["initiative"]

        # 4. Social Layer
        social_result = self.social.update(context)
        context = context.evolve(
            social_snapshot=social_result["snapshot"],
            social_alignment=social_result["alignment"],
            cooperative_adjustments=social_result["adjustments"]
        )
        social_alignment = social_result["alignment"]
        cooperative_adjustments = social_result["adjustments"]

        # 5. Culture Layer
        culture_result = self.culture.update(context)
        context = context.evolve(
            culture_snapshot=culture_result["snapshot"],
            cultural_alignment=culture_result["alignment"],
            civilization_adjustments=culture_result["adjustments"]
        )
        cultural_alignment = culture_result["alignment"]
        civilization_adjustments = culture_result["adjustments"]

        # 6. Derived Engines Layer
        militocracy_result = self.militocracy.update(context)
        synergy_result = self.synergy.update(context)

        context = context.evolve(
            militocracy_snapshot=militocracy_result["snapshot"],
            synergy_snapshot=synergy_result["snapshot"]
        )

        discipline_snapshot = militocracy_result["trace_snapshot"]
        synergy_snapshot = synergy_result["trace_snapshot"]

        # 7. Values Layer
        values_result = self.values.update(context)
        context = context.evolve(
            values_snapshot=values_result["snapshot"],
            value_alignment=values_result["value_alignment"]
        )
        value_alignment = float(values_result.get("value_alignment", self.values.valuealignmentscore))

        # 8. Autonomy Layer
        autonomy_result = self.autonomy.update(context)
        context = context.evolve(
            autonomy_snapshot=autonomy_result["snapshot"],
            primary_strategy=autonomy_result["primary_strategy"],
            strategies=autonomy_result["strategies"]
        )
        primary_strategy = autonomy_result["primary_strategy"]
        strategies = autonomy_result["strategies"]

        # 9. Intent Layer
        intent_result = self.intentengine.update(context)
        context = context.evolve(
            intent_snapshot=intent_result["snapshot"],
            primary_intent=intent_result["primary_intent"],
            intents=intent_result["intents"]
        )
        primary_intent = intent_result["primary_intent"]
        intents = intent_result["intents"]

        # 10. Planning Layer
        choice, candidates, evaluated = self._plan_action(
            state, initiative, primary_intent, primary_strategy, metafeedback
        )

        # 11. World Step
        state_before = state.world_state if isinstance(state.world_state, dict) else {}
        transition = self.world.step(choice.action)
        state_after = self.world.state()
        self.causal_graph.record_transition(state_before, choice.action, state_after)

        # 12. Trace & Feedback Layer
        return self._finalize_step(
            state, choice, analysis, metafeedback, self_snapshot,
            initiative, intents, primary_intent, strategies, primary_strategy,
            value_alignment,
            social_alignment, cooperative_adjustments,
            cultural_alignment, civilization_adjustments,
            discipline_snapshot, synergy_snapshot,
            transition
        )

    def _plan_action(
        self,
        state: AgentState,
        initiative: dict[str, Any],
        primary_intent: dict[str, Any] | None,
        primary_strategy: dict[str, Any] | None,
        metafeedback: dict[str, Any]
    ) -> tuple[Any, list[Any], Any]:
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
        return choice, candidates, evaluated

    def _finalize_step(
        self,
        state: AgentState,
        choice: Any,
        analysis: dict[str, Any],
        metafeedback: dict[str, Any],
        self_snapshot: dict[str, Any],
        initiative: dict[str, Any],
        intents: list[dict[str, Any]],
        primary_intent: dict[str, Any] | None,
        strategies: list[dict[str, Any]],
        primary_strategy: dict[str, Any] | None,
        value_alignment: float,
        social_alignment: float,
        cooperative_adjustments: dict[str, Any],
        cultural_alignment: float,
        civilization_adjustments: dict[str, Any],
        discipline_snapshot: dict[str, Any],
        synergy_snapshot: dict[str, Any],
        transition: dict[str, Any]
    ) -> dict[str, Any]:

        # Phase 13: Manual application of corrections for non-self-layer components
        # Orientation is already updated via update(context) using metafeedback
        # SelfModel metrics are updated via update(context) in the next cycle (or handled internally)

        # Apply corrections to Planner and MetaObserver (thresholds)
        # Using suggest_corrections to get values without side effects
        corrections = self.metacognition.suggest_corrections()

        # Apply Planner corrections
        planner_patch = corrections.get("planner", {})
        if planner_patch:
             current_meta_weight = float(getattr(self.planner, "meta_alignment_weight", 0.15))
             self.planner.meta_alignment_weight = float(planner_patch.get("metaalignmentweight", current_meta_weight))

        # Apply MetaObserver corrections
        observer_patch = corrections.get("observer", {})
        if observer_patch.get("raise_thresholds"):
             current = float(getattr(self.meta_observer, "self_consistency_threshold", 0.45))
             self.meta_observer.self_consistency_threshold = max(0.35, min(0.7, current + 0.06)) # correction_strength hardcoded to match MetaCognition default

        # Phase 13: self_model.update(context) handles metric updates and cognitive trace in the next cycle
        # by observing the history and snapshots.
        # We assume self_model.update() was called at start of step.
        # But wait, cognitive trace for THIS action needs to be recorded?
        # Yes, SelfModel.update() in the NEXT step will see the new history event appended below.

        if choice.confidence < self.low_confidence_threshold:
            self.signal_bus.emit(
                InternalSignal(
                    signal_type="low_confidence",
                    t=state.t,
                    payload={"confidence": choice.confidence, "action": choice.action},
                )
            )

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
            "value_alignment": value_alignment,
            "social_alignment": social_alignment,
            "cooperative_adjustments": cooperative_adjustments,
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
                "militocracyalignmentscore": self.identitycore.militocracyalignmentscore,
                "synergyalignmentscore": self.identitycore.synergyalignmentscore,
            },
            "social": {
                "social_models": dict(self.social.social_models),
                "collectivevaluealignment": self.social.collectivevaluealignment,
                "collectiveintentalignment": self.social.collectiveintentalignment,
                "socialconflictscore": self.social.socialconflictscore,
                "cooperation_score": self.social.cooperation_score,
                "group_norms": dict(self.social.group_norms),
                "tradition_patterns": (
                    [dict(p) for p in self.social.tradition_patterns[-20:]]
                    if isinstance(self.social.tradition_patterns, list)
                    else dict(self.social.tradition_patterns)
                ),
                "culturalsimilarityscore": self.social.culturalsimilarityscore,
            },
            "culture": {
                "norms": dict(self.culture.norms),
                "traditions": (
                    [dict(t) for t in self.culture.traditions[-20:]]
                    if isinstance(self.culture.traditions, list)
                    else dict(self.culture.traditions)
                ),
                "culture_trace": list(self.culture.culture_trace[-20:]),
                "norm_conflicts": [dict(c) for c in self.culture.norm_conflicts],
                "civilization_state": dict(self.culture.civilization_state),
            },
            "militocracy": {
                "militarydisciplinescore": self.militocracy.militarydisciplinescore,
                "command_coherence": self.militocracy.command_coherence,
                "discipline_bias": self.militocracy.discipline_bias,
                "discipline_trace": list(self.militocracy.discipline_trace[-20:]),
                "snapshot": discipline_snapshot,
            },
            "synergy": {
                "synergy_index": self.synergy.synergy_index,
                "cooperative_efficiency": self.synergy.cooperative_efficiency,
                "collective_synergy": self.synergy.collective_synergy,
                "synergy_trace": list(self.synergy.synergy_trace[-20:]),
                "snapshot": synergy_snapshot,
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
