from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .assembly import AgentState, AssemblyPoint
from .causal import CausalGraph
from .meta_observer import MetaObserver
from .meta_cognition import MetaCognitionEngine
from .orientation import OrientationCenter
from .self_model import SelfModel
from .signals import InternalSignal, SignalBus
from .trajectories import TrajectoryPlanner
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

        candidates = self.planner.generate(self.world, state)
        evaluated = self.planner.evaluate(
            candidates,
            state,
            collective_state=self.collective_state,
            self_model=self.self_model,
            metafeedback=metafeedback,
        )
        choice = self.planner.choose(evaluated)

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
            "analysis": analysis,
            "confidence": choice.confidence,
            "uncertainty": choice.uncertainty,
            "causal_score": choice.causal_score,
            "causal_graph": self.causal_graph.to_dict(),
            "self_model": self.self_model.to_dict(),
            "self_model_snapshot": self_snapshot,
            "metacognition": metafeedback,
            "signals": [
                {"type": s.signal_type, "payload": s.payload}
                for s in self.signal_bus.get_recent(clear=True)
            ],
            **transition,
        }
        self.assembly.append_history(event)
        self.assembly.prune_history()
        return event
