from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .rhythm_engine import RhythmEngine, RhythmInputs, RhythmPhase


@dataclass(frozen=True)
class OrientationOutput:
    rhythm_phase: RhythmPhase
    chaos_score: float
    harmony_score: float
    delta: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "rhythm_phase": self.rhythm_phase,
            "chaos_score": self.chaos_score,
            "harmony_score": self.harmony_score,
            "delta": self.delta,
        }


class OrientationCenter:
    """
    Phase 13 - Orientation Center

    Skeleton: computes rhythm phase only (no side effects).
    """

    def __init__(self, *, hold_epsilon: float = 0.1, rhythm_engine: RhythmEngine | None = None) -> None:
        self.rhythm_engine = rhythm_engine or RhythmEngine(hold_epsilon=hold_epsilon)

    def evaluate(self, inputs: RhythmInputs) -> OrientationOutput:
        result = self.rhythm_engine.evaluate(inputs)
        return OrientationOutput(
            rhythm_phase=result["rhythm_phase"],
            chaos_score=result["chaos_score"],
            harmony_score=result["harmony_score"],
            delta=result["delta"],
        )
