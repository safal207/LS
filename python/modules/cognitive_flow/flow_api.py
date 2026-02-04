from __future__ import annotations

from typing import Any, Optional

from .presence import PresenceState
from .transition_engine import TransitionEngine


class CognitiveFlow:
    def __init__(self, presence: PresenceState, transitions: TransitionEngine) -> None:
        self.presence = presence
        self.transitions = transitions

    def step(self, event: Optional[Any] = None) -> None:
        if not isinstance(event, dict):
            return None

        event_type = event.get("type")
        if not event_type:
            return None

        advance = False
        if event_type in {"input_received", "llm_started", "llm_finished", "output_ready"}:
            advance = True
        elif event_type == "state_change" and event.get("state") == "responding":
            advance = True

        if not advance:
            return None

        current = self.presence.phase
        next_phase = self.transitions.next_phase(current)
        if not next_phase:
            return None

        liminal = self.transitions.enter_liminal(current, next_phase)
        if liminal:
            self.presence.phase = liminal
            self.presence.metadata["liminal"] = liminal
        else:
            self.presence.metadata.pop("liminal", None)

        self.presence.phase = next_phase
        return next_phase
