from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .state import StateSnapshot
from .transitions import StateTransitionEngine


@dataclass
class PresenceMonitor:
    engine: StateTransitionEngine = field(default_factory=StateTransitionEngine)
    history: List[StateSnapshot] = field(default_factory=list)

    def update(
        self,
        *,
        capu_features: Dict[str, Any],
        metrics: Dict[str, Any],
        hardware: Dict[str, Any],
    ) -> StateSnapshot:
        snapshot = self.engine.update(
            capu_features=capu_features,
            metrics=metrics,
            hardware=hardware,
        )
        self.history.append(snapshot)
        return snapshot

    @property
    def current_state(self) -> StateSnapshot:
        return self.engine.current
