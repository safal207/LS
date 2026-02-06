from __future__ import annotations

from typing import Dict


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


class FieldDampening:
    """
    Phase 18.1 - Distributed Drift Dampening
    Applies EMA smoothing to field metrics.
    """

    def __init__(self, alpha: float = 0.3) -> None:
        self.alpha = float(alpha)
        self._state: Dict[str, float] = {}

    def apply(self, metrics: Dict[str, float]) -> Dict[str, float]:
        if not metrics:
            return {}

        smoothed: Dict[str, float] = {}
        for key, value in metrics.items():
            current = _clamp(float(value))
            previous = self._state.get(key, current)
            updated = (self.alpha * current) + ((1.0 - self.alpha) * previous)
            updated = _clamp(updated)
            smoothed[key] = updated
            self._state[key] = updated
        return smoothed
