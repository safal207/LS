from __future__ import annotations

from typing import Dict


def _clamp(value: float, low: float = -0.1, high: float = 0.1) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


class FieldReflexivity:
    """
    Phase 26 - Reflexive Cognitive Field
    Tracks temporal changes in metrics and applies gentle corrections
    to maintain meta-stability.
    """

    def __init__(self, lr: float = 0.05) -> None:
        self.lr = float(lr)
        self.prev: Dict[str, float] = {}
        self.trend: Dict[str, float] = {}

    def update(self, metrics: Dict[str, float]) -> Dict[str, float]:
        """
        Computes trend (first derivative) and updates internal state.
        Returns a dict of reflexive adjustments.
        """
        if not metrics:
            return {}

        adjustments: Dict[str, float] = {}
        for key, value in metrics.items():
            current = float(value)
            previous = self.prev.get(key)
            if previous is None:
                trend = 0.0
            else:
                trend = current - previous
            self.trend[key] = trend
            adjustment = _clamp(-self.lr * trend)
            adjustments[key] = adjustment
            self.prev[key] = current
        return adjustments
