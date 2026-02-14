from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .assembly import AgentState, AssemblyPoint
from .meta_observer import MetaObserver
from .orientation import OrientationCenter
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
    history: list[dict[str, Any]] = field(default_factory=list)

    def build_state(self) -> AgentState:
        return self.assembly.build(
            t=self.world.t,
            world_state=self.world.state(),
            orientation=self.orientation,
            history=self.history,
        )

    def step(self) -> dict[str, Any]:
        """Execute one decision cycle and return structured step output."""
        state = self.build_state()

        # TODO: integrate NCA with Web4Session observability events
        analysis = self.meta_observer.observe_and_correct(state, self.orientation)

        candidates = self.planner.generate(self.world, state)
        evaluated = self.planner.evaluate(candidates, state)
        choice = self.planner.choose(evaluated)

        # TODO: integrate NCA with transport-level lifecycle hooks
        transition = self.world.step(choice.action)

        event = {
            "t": transition["t"],
            "action": choice.action,
            "score": choice.score,
            "analysis": analysis,
            **transition,
        }
        self.history.append(event)
        return event
