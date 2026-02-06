from __future__ import annotations

from typing import Dict


def _clamp(value: float, low: float = -0.2, high: float = 0.2) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


class FieldCoordination:
    """
    Phase 19 - Field-Driven Coordination
    Computes a small coordination bias from field metrics.
    """

    def __init__(self, weight: float = 0.15) -> None:
        self.weight = float(weight)

    def compute(self, metrics: Dict[str, float]) -> float:
        if not metrics:
            return 0.0
        tension = float(metrics.get("trajectory_tension", 0.0))
        coherence = float(metrics.get("orientation_coherence", 0.0))
        bias = self.weight * (tension - coherence)
        return _clamp(bias)
