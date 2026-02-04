from __future__ import annotations

from typing import Optional, Dict

from .liminal import resolve_liminal

PHASE_ORDER = ("perceive", "interpret", "analyze", "plan", "act", "reflect")
PHASE_INDEX: Dict[str, int] = {phase: idx for idx, phase in enumerate(PHASE_ORDER)}


class TransitionEngine:
    def next_phase(self, current_phase: Optional[str]) -> Optional[str]:
        if current_phase is None:
            return PHASE_ORDER[0]
        idx = PHASE_INDEX.get(current_phase)
        if idx is None:
            return None
        return PHASE_ORDER[(idx + 1) % len(PHASE_ORDER)]

    def enter_liminal(self, from_phase: Optional[str], to_phase: Optional[str]) -> Optional[str]:
        liminal = resolve_liminal(from_phase, to_phase)
        return liminal.name if liminal else None

    def complete_phase(self, phase: Optional[str]) -> None:
        return None
