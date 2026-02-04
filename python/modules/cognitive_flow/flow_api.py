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
            return

        try:
            event_type = event.get("type")
            if not event_type:
                return

            payload = event.get("payload") or {}
            current = self.presence.phase

            # 1) Explicit transition signal: advance to next phase.
            if payload.get("transition_signal"):
                next_phase = self.transitions.next_phase(current)
                if not next_phase:
                    return
                liminal = self.transitions.enter_liminal(current, next_phase)
                if liminal:
                    self.presence.phase = liminal
                else:
                    self.presence.phase = next_phase
                return

            # 2) Event-driven defaults.
            if event_type in {"input", "input_received"}:
                self.presence.phase = "perceive"
                return

            if event_type in {"llm_call", "llm_started"}:
                next_phase = self.transitions.next_phase("interpret")
                liminal = self.transitions.enter_liminal("interpret", next_phase)
                self.presence.phase = liminal or next_phase
                return

            if event_type in {"output", "output_ready"}:
                self.presence.phase = "act"
                return

            if event_type in {"task_complete"} or (event_type == "state_change" and event.get("state") == "idle"):
                self.presence.phase = "reflect"
                return

            # 3) If phase is still unset, start with perceive.
            if self.presence.phase is None:
                self.presence.phase = "perceive"
        except Exception:
            # Cognitive Flow - best-effort
            return
