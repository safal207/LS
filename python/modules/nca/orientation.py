from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OrientationCenter:
    """Stores identity anchors and preferences for NCA decision-making.

    Attributes:
        identity: Stable identity label for the agent instance.
        invariants: Non-negotiable constraints to avoid identity drift.
        preferences: Soft optimization criteria used for trajectory scoring.
    """

    identity: str
    invariants: dict[str, Any] = field(default_factory=dict)
    preferences: dict[str, float] = field(default_factory=dict)

    def update_from_feedback(self, feedback: dict[str, Any]) -> None:
        """Update preferences and optionally invariants from feedback.

        Expected feedback keys (all optional):
            preference_updates: mapping of preference -> delta
            invariant_updates: mapping of invariant -> new value
        """
        preference_updates = feedback.get("preference_updates", {})
        for key, delta in preference_updates.items():
            current = float(self.preferences.get(key, 0.0))
            self.preferences[key] = current + float(delta)

        invariant_updates = feedback.get("invariant_updates", {})
        for key, value in invariant_updates.items():
            self.invariants[key] = value

    # Compatibility with requested interface naming.
    def updatefromfeedback(self, feedback: dict[str, Any]) -> None:
        """Alias for update_from_feedback to match requested minimal interface."""
        self.update_from_feedback(feedback)
