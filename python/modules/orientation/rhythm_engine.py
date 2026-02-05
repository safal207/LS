from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


RhythmPhase = Literal["inhale", "hold", "exhale"]


@dataclass(frozen=True)
class RhythmInputs:
    diversity_score: float
    stability_score: float
    contradiction_rate: float
    drift_pressure: float
    confidence_budget: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RhythmInputs":
        return cls(
            diversity_score=float(data.get("diversity_score", 0.0)),
            stability_score=float(data.get("stability_score", 0.0)),
            contradiction_rate=float(data.get("contradiction_rate", 0.0)),
            drift_pressure=float(data.get("drift_pressure", 0.0)),
            confidence_budget=float(data.get("confidence_budget", 0.0)),
        )


class RhythmEngine:
    """
    Phase 13 - Rhythm Engine (inhale / hold / exhale)

    Skeleton: computes a phase signal only.
    """

    def __init__(self, *, hold_epsilon: float = 0.1) -> None:
        self.hold_epsilon = hold_epsilon

    def evaluate(self, inputs: RhythmInputs) -> dict[str, Any]:
        chaos = max(0.0, inputs.diversity_score) + max(0.0, inputs.contradiction_rate) + max(0.0, inputs.drift_pressure)
        harmony = max(0.0, inputs.stability_score) + max(0.0, inputs.confidence_budget)
        delta = chaos - harmony

        if abs(delta) <= self.hold_epsilon:
            phase: RhythmPhase = "hold"
        elif delta > 0:
            phase = "inhale"
        else:
            phase = "exhale"

        return {
            "rhythm_phase": phase,
            "chaos_score": chaos,
            "harmony_score": harmony,
            "delta": delta,
        }
