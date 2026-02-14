from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .assembly import AgentState
from .orientation import OrientationCenter


@dataclass
class MetaObserver:
    """Monitors state for drift and emits orientation feedback."""

    drift_threshold: int = 2

    def analyze(self, state: AgentState) -> dict[str, Any]:
        """Return analysis signals from current state and recent behavior."""
        drift_count = 0
        current_world = state.world_state
        current_pos = current_world.get("agent_position") if isinstance(current_world, dict) else None

        for event in state.history[-5:]:
            if event.get("action") == "idle":
                drift_count += 1
            if current_pos is not None and event.get("position_before") == current_pos:
                drift_count += 1

        return {
            "identity_drift_risk": drift_count >= self.drift_threshold,
            "drift_count": drift_count,
        }

    def stabilize(self, orientation: OrientationCenter, analysis: dict[str, Any]) -> None:
        """Apply corrective feedback to reduce identity drift risk."""
        if not analysis.get("identity_drift_risk"):
            return
        orientation.update_from_feedback(
            {
                "preference_updates": {"progress": 0.2, "stability": 0.1},
                "invariant_updates": {"avoid_idle_loops": True},
            }
        )

    def observe_and_correct(self, state: AgentState, orientation: OrientationCenter) -> dict[str, Any]:
        """Convenience wrapper: analyze state and apply correction if needed."""
        analysis = self.analyze(state)
        self.stabilize(orientation, analysis)
        return analysis
