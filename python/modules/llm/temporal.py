from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Literal

State = Literal["idle", "listening", "thinking", "responding"]


@dataclass
class TemporalContext:
    state: State = "idle"
    last_transition: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def transition(self, new_state: State) -> None:
        self.state = new_state
        self.last_transition = time.time()

    def age(self) -> float:
        return time.time() - self.last_transition
