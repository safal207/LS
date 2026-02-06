from __future__ import annotations

from .metrics import clamp


class TrajectoryAdapter:
    """
    Phase 14.2 - Trajectory Adapter
    Converts trajectory_error into an orientation-friendly signal.
    Skeleton: identity transform with clamping.
    """

    def evaluate(self, trajectory_error: float | None) -> float:
        if trajectory_error is None:
            return 0.0
        return clamp(float(trajectory_error))
