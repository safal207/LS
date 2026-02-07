from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class SystemState(Enum):
    STABLE = "stable"
    UNCERTAIN = "uncertain"
    OVERLOAD = "overload"
    DIFFUSE_FOCUS = "diffuse_focus"
    FRAGMENTED = "fragmented"
    TRANSITION = "transition"


@dataclass(frozen=True)
class StateSnapshot:
    state: SystemState
    context: Dict[str, Any]
    timestamp: str
