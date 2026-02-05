from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .rhythm_engine import RhythmEngine, RhythmInputs, RhythmPhase
from .metabolic_diversity import MetabolicDiversity
from .belief_aging import BeliefAging
from .temporal_causality import TemporalCausality
from .cognitive_immunity import CognitiveImmunity
from .conviction_regulator import ConvictionRegulator


@dataclass(frozen=True)
class OrientationOutput:
    rhythm_phase: RhythmPhase
    chaos_score: float
    harmony_score: float
    delta: float
    diversity_score: float
    stability_score: float
    contradiction_rate: float
    drift_pressure: float
    confidence_budget: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "rhythm_phase": self.rhythm_phase,
            "chaos_score": self.chaos_score,
            "harmony_score": self.harmony_score,
            "delta": self.delta,
            "diversity_score": self.diversity_score,
            "stability_score": self.stability_score,
            "contradiction_rate": self.contradiction_rate,
            "drift_pressure": self.drift_pressure,
            "confidence_budget": self.confidence_budget,
        }


class OrientationCenter:
    """
    Phase 13 - Orientation Center

    Skeleton: computes orientation signals only (no side effects).
    """

    def __init__(
        self,
        *,
        hold_epsilon: float = 0.1,
        rhythm_engine: RhythmEngine | None = None,
        metabolic_diversity: MetabolicDiversity | None = None,
        belief_aging: BeliefAging | None = None,
        temporal_causality: TemporalCausality | None = None,
        cognitive_immunity: CognitiveImmunity | None = None,
        conviction_regulator: ConvictionRegulator | None = None,
    ) -> None:
        self.rhythm_engine = rhythm_engine or RhythmEngine(hold_epsilon=hold_epsilon)
        self.metabolic_diversity = metabolic_diversity or MetabolicDiversity()
        self.belief_aging = belief_aging or BeliefAging()
        self.temporal_causality = temporal_causality or TemporalCausality()
        self.cognitive_immunity = cognitive_immunity or CognitiveImmunity()
        self.conviction_regulator = conviction_regulator or ConvictionRegulator()

    def evaluate(
        self,
        *,
        history_stats: dict[str, Any] | None = None,
        beliefs: list[dict[str, Any]] | None = None,
        temporal_metrics: dict[str, Any] | None = None,
        immunity_signals: dict[str, Any] | None = None,
        conviction_inputs: dict[str, Any] | None = None,
    ) -> OrientationOutput:
        diversity_score = self.metabolic_diversity.evaluate(history_stats)
        stability_score = self.belief_aging.evaluate(beliefs)
        contradiction_rate = self.temporal_causality.evaluate(temporal_metrics)
        drift_pressure = self.cognitive_immunity.evaluate(immunity_signals)
        confidence_budget = self.conviction_regulator.evaluate(conviction_inputs)

        rhythm_inputs = RhythmInputs(
            diversity_score=diversity_score,
            stability_score=stability_score,
            contradiction_rate=contradiction_rate,
            drift_pressure=drift_pressure,
            confidence_budget=confidence_budget,
        )
        rhythm_result = self.rhythm_engine.evaluate(rhythm_inputs)

        return OrientationOutput(
            rhythm_phase=rhythm_result["rhythm_phase"],
            chaos_score=rhythm_result["chaos_score"],
            harmony_score=rhythm_result["harmony_score"],
            delta=rhythm_result["delta"],
            diversity_score=diversity_score,
            stability_score=stability_score,
            contradiction_rate=contradiction_rate,
            drift_pressure=drift_pressure,
            confidence_budget=confidence_budget,
        )
