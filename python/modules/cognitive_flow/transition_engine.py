from __future__ import annotations

from typing import Optional


class TransitionEngine:
    def next_phase(self, current_phase: Optional[str]) -> Optional[str]:
        return None

    def enter_liminal(self, from_phase: Optional[str], to_phase: Optional[str]) -> Optional[str]:
        return None

    def complete_phase(self, phase: Optional[str]) -> None:
        return None
