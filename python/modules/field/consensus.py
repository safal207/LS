from __future__ import annotations

from typing import Dict


def _clamp(value: float, low: float = -0.15, high: float = 0.15) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


class ConsensusEngine:
    """
    Phase 20 - Multi-Agent Consensus Engine
    Computes a consensus adjustment based on field metrics and local mode.
    """

    def __init__(self, strength: float = 0.1) -> None:
        self.strength = float(strength)

    def compute(self, metrics: Dict[str, float], local_mode: str, local_confidence: float) -> float:
        if not metrics:
            return 0.0

        alignment = float(metrics.get("confidence_alignment", 0.0))
        coherence = float(metrics.get("orientation_coherence", 0.0))

        pull = 0.0
        if local_mode == "B":
            pull += alignment
            pull -= coherence
        elif local_mode == "A":
            pull -= alignment
            pull += coherence

        adjustment = self.strength * pull
        return _clamp(adjustment)
