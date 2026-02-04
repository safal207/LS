from __future__ import annotations

from typing import Any, Optional

from .presence import PresenceState
from .transition_engine import TransitionEngine


class CognitiveFlow:
    def __init__(self, presence: PresenceState, transitions: TransitionEngine) -> None:
        self.presence = presence
        self.transitions = transitions

    def step(self, event: Optional[Any] = None) -> None:
        return None
