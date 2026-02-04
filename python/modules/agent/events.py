from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Literal

EventType = Literal[
    "input_received",
    "llm_started",
    "llm_finished",
    "output_ready",
    "state_change",
    "phase_transition",
    "cancelled",
    "metrics",
    "error",
]


@dataclass
class AgentEvent:
    type: EventType
    timestamp: float = field(default_factory=time.time)
    payload: Dict[str, Any] = field(default_factory=dict)
