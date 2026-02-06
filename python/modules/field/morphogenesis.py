from __future__ import annotations

from typing import Dict


def _clamp(value: float, low: float = 0.5, high: float = 1.5) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


class FieldMorphogenesis:
    """
    Phase 23 - Autonomous Field Morphogenesis
    Dynamically reshapes field structure based on mesh patterns and long-term trends.
    """

    def __init__(self, lr: float = 0.02) -> None:
        self.lr = float(lr)
        self.morphology: Dict[str, float] = {
            "coherence_scale": 1.0,
            "alignment_scale": 1.0,
            "tension_scale": 1.0,
        }

    def update(self, mesh: Dict[str, float], metrics: Dict[str, float]) -> Dict[str, float]:
        """
        Updates morphology based on mesh patterns and field metrics.
        """
        if not metrics:
            return dict(self.morphology)

        coherence_metric = float(metrics.get("orientation_coherence", 0.0))
        alignment_metric = float(metrics.get("confidence_alignment", 0.0))
        tension_metric = float(metrics.get("trajectory_tension", 0.0))

        coherence_pattern = float(mesh.get("coherence_pattern", 0.0))
        alignment_pattern = float(mesh.get("alignment_pattern", 0.0))
        tension_pattern = float(mesh.get("tension_pattern", 0.0))

        coherence_target = 0.5 * coherence_pattern + 0.5 * coherence_metric
        alignment_target = 0.5 * alignment_pattern + 0.5 * alignment_metric
        tension_target = 0.5 * tension_pattern + 0.5 * tension_metric

        self.morphology["coherence_scale"] = _clamp(
            self.morphology["coherence_scale"]
            + (self.lr * (coherence_target - self.morphology["coherence_scale"]))
        )
        self.morphology["alignment_scale"] = _clamp(
            self.morphology["alignment_scale"]
            + (self.lr * (alignment_target - self.morphology["alignment_scale"]))
        )
        self.morphology["tension_scale"] = _clamp(
            self.morphology["tension_scale"]
            + (self.lr * (tension_target - self.morphology["tension_scale"]))
        )

        return dict(self.morphology)
