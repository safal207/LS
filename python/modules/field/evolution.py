from __future__ import annotations

from typing import Dict


def _clamp(value: float, low: float = 0.5, high: float = 2.0) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


class FieldEvolution:
    """
    Phase 21 - Self-Evolving Field Dynamics
    Adjusts internal field parameters based on long-term trends.
    """

    def __init__(self, lr: float = 0.05) -> None:
        self.lr = float(lr)
        self.state: Dict[str, float] = {
            "coherence_weight": 1.0,
            "alignment_weight": 1.0,
            "tension_weight": 1.0,
        }

    def update(self, metrics: Dict[str, float]) -> Dict[str, float]:
        if not metrics:
            return dict(self.state)

        coherence = float(metrics.get("orientation_coherence", 0.0))
        alignment = float(metrics.get("confidence_alignment", 0.0))
        tension = float(metrics.get("trajectory_tension", 0.0))

        self.state["coherence_weight"] = _clamp(
            self.state["coherence_weight"] + (self.lr * (coherence - 0.5))
        )
        self.state["alignment_weight"] = _clamp(
            self.state["alignment_weight"] + (self.lr * (alignment - 0.5))
        )
        self.state["tension_weight"] = _clamp(
            self.state["tension_weight"] + (self.lr * (tension - 0.5))
        )

        return dict(self.state)
