from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentState:
    goal: str
    context: dict[str, Any]
    progress_score: float = 0.0
    goal_completion: float = 0.0


@dataclass
class StateTracker:
    _previous: AgentState | None = None
    _current: AgentState | None = None
    history: list[AgentState] = field(default_factory=list)

    def update(self, state: AgentState) -> None:
        self._previous = self._current
        self._current = state
        self.history.append(state)

    def previous_state(self) -> AgentState | None:
        return self._previous

    def current_state(self) -> AgentState | None:
        return self._current
