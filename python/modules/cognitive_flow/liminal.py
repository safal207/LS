from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Tuple


@dataclass
class LiminalState:
    name: str
    from_phase: Optional[str]
    to_phase: Optional[str]


DEFAULT_LIMINALS: Dict[Tuple[str, str], str] = {
    ("perceive", "interpret"): "interpreting",
    ("analyze", "plan"): "validating",
    ("act", "reflect"): "checking",
}


def resolve_liminal(from_phase: Optional[str], to_phase: Optional[str]) -> Optional[LiminalState]:
    if not from_phase or not to_phase:
        return None
    name = DEFAULT_LIMINALS.get((from_phase, to_phase))
    if not name:
        return None
    return LiminalState(name=name, from_phase=from_phase, to_phase=to_phase)
