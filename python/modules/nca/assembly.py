from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from .orientation import OrientationCenter
from .signals import InternalSignal, SignalBus


@dataclass
class AgentState:
    """Unified state snapshot consumed by planning and supervision layers."""

    t: int
    world_state: Any
    self_state: dict[str, Any]
    history: list[dict[str, Any]] = field(default_factory=list)


class AssemblyPoint:
    """Builds AgentState by assembling world and self snapshots."""

    def __init__(self, *, max_history: int = 50) -> None:
        self.max_history = max_history
        self.history: deque[dict[str, Any]] = deque(maxlen=max_history)
        self.micro_goals: list[dict[str, Any]] = []

    def append_history(self, event: dict[str, Any]) -> None:
        self.history.append(event)

    def prune_history(self) -> None:
        """Compatibility hook for explicit FIFO pruning policy."""
        while len(self.history) > self.max_history:
            self.history.popleft()

    def update_micro_goals(
        self,
        world_state: Any,
        orientation: OrientationCenter,
        signal_bus: SignalBus | None = None,
    ) -> list[dict[str, Any]]:
        if not isinstance(world_state, dict):
            return list(self.micro_goals)

        current_pos = int(world_state.get("agent_position", 0))
        goal_pos = int(world_state.get("goal_position", current_pos))
        previous_pos = world_state.get("previous_agent_position")

        if previous_pos is not None and previous_pos != current_pos:
            target = min(current_pos + 1, goal_pos)
            candidate = {"type": "stabilize_progress", "target_position": target}
            if candidate not in self.micro_goals and target != current_pos:
                self.micro_goals.append(candidate)

        completed: list[dict[str, Any]] = []
        for item in self.micro_goals:
            if current_pos >= int(item.get("target_position", current_pos + 1)):
                completed.append(item)
        for item in completed:
            self.micro_goals.remove(item)

        if orientation.invariants.get("hold_position") and self.micro_goals:
            if signal_bus is not None:
                signal_bus.emit(
                    InternalSignal(
                        signal_type="trajectory_conflict",
                        payload={
                            "reason": "micro-goals conflict with hold_position invariant",
                            "micro_goals": list(self.micro_goals),
                        },
                    )
                )

        return list(self.micro_goals)

    # Compatibility aliases required by specification.
    def updatemicrogoals(
        self,
        world_state: Any,
        orientation: OrientationCenter,
        signal_bus: SignalBus | None = None,
    ) -> list[dict[str, Any]]:
        return self.update_micro_goals(world_state, orientation, signal_bus)

    def build(
        self,
        *,
        t: int,
        world_state: Any,
        orientation: OrientationCenter,
        signal_bus: SignalBus | None = None,
    ) -> AgentState:
        micro_goals = self.update_micro_goals(world_state, orientation, signal_bus)
        self_state = {
            "identity": orientation.identity,
            "invariants": dict(orientation.invariants),
            "preferences": dict(orientation.preferences),
            "personality": orientation.personality_profile(),
            "micro_goals": micro_goals,
        }
        return AgentState(t=t, world_state=world_state, self_state=self_state, history=list(self.history))
