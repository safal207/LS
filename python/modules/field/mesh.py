from __future__ import annotations

from typing import Dict


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


class CognitiveMesh:
    """
    Phase 22 - Cognitive Mesh
    Extracts and reinforces stable distributed patterns from field metrics.
    """

    def __init__(self, lr: float = 0.03) -> None:
        self.lr = float(lr)
        self.mesh_state: Dict[str, float] = {
            "coherence_pattern": 0.0,
            "alignment_pattern": 0.0,
            "tension_pattern": 0.0,
        }

    def update(self, metrics: Dict[str, float]) -> Dict[str, float]:
        """
        Updates mesh_state using slow EMA-like reinforcement.
        """
        if not metrics:
            return dict(self.mesh_state)

        coherence = float(metrics.get("orientation_coherence", 0.0))
        alignment = float(metrics.get("confidence_alignment", 0.0))
        tension = float(metrics.get("trajectory_tension", 0.0))

        self.mesh_state["coherence_pattern"] = _clamp(
            self.mesh_state["coherence_pattern"]
            + (self.lr * (coherence - self.mesh_state["coherence_pattern"]))
        )
        self.mesh_state["alignment_pattern"] = _clamp(
            self.mesh_state["alignment_pattern"]
            + (self.lr * (alignment - self.mesh_state["alignment_pattern"]))
        )
        self.mesh_state["tension_pattern"] = _clamp(
            self.mesh_state["tension_pattern"]
            + (self.lr * (tension - self.mesh_state["tension_pattern"]))
        )

        return dict(self.mesh_state)
