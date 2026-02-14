from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .assembly import AgentState, AssemblyPoint
from .meta_observer import MetaObserver
from .orientation import OrientationCenter
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
    signal_bus: SignalBus = field(default_factory=SignalBus)
    signal_log: list[dict[str, Any]] = field(default_factory=list)
    low_confidence_threshold: float = 0.35

    def __post_init__(self) -> None:
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

        analysis = self.meta_observer.observe_and_correct(state, self.orientation, self.signal_bus)

        candidates = self.planner.generate(self.world, state)
        evaluated = self.planner.evaluate(candidates, state)
        choice = self.planner.choose(evaluated)

        if choice.confidence < self.low_confidence_threshold:
            self.signal_bus.emit(
                InternalSignal(
                    signal_type="low_confidence",
                    t=state.t,
                    payload={"confidence": choice.confidence, "action": choice.action},
                )
            )

        transition = self.world.step(choice.action)

        event = {
            "t": transition["t"],
            "action": choice.action,
            "score": choice.score,
            "analysis": analysis,
            "confidence": choice.confidence,
            "uncertainty": choice.uncertainty,
            "signals": [
                {"type": s.signal_type, "payload": s.payload}
                for s in self.signal_bus.get_recent(clear=True)
            ],
            **transition,
        }
        self.assembly.append_history(event)
        self.assembly.prune_history()
        return event
