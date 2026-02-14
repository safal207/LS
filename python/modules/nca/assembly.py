from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .orientation import OrientationCenter


@dataclass
class AgentState:
    """Unified state snapshot consumed by planning and supervision layers."""

    t: int
    world_state: Any
    self_state: dict[str, Any]
    history: list[dict[str, Any]] = field(default_factory=list)


class AssemblyPoint:
    """Builds AgentState by assembling world and self snapshots."""

    def build(
        self,
        *,
        t: int,
        world_state: Any,
        orientation: OrientationCenter,
        history: list[dict[str, Any]],
    ) -> AgentState:
        self_state = {
            "identity": orientation.identity,
            "invariants": dict(orientation.invariants),
            "preferences": dict(orientation.preferences),
        }
        return AgentState(t=t, world_state=world_state, self_state=self_state, history=list(history))
