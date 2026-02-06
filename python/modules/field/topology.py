from __future__ import annotations

from typing import Dict, Tuple

PAIRS = [
    ("orientation_coherence", "confidence_alignment"),
    ("orientation_coherence", "trajectory_tension"),
    ("confidence_alignment", "trajectory_tension"),
]


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


def _metric_base(metric: str) -> str:
    return (
        metric.replace("orientation_", "")
        .replace("confidence_", "")
        .replace("trajectory_", "")
    )


class CognitiveTopology:
    """
    Phase 24 - Emergent Cognitive Topology
    Maintains a small connectivity graph between field metrics and
    applies topological influence to metric propagation.
    """

    def __init__(self, lr: float = 0.05) -> None:
        self.lr = float(lr)
        self.edges: Dict[Tuple[str, str], float] = {}

    def update(self, metrics: Dict[str, float], mesh: Dict[str, float]) -> Dict[Tuple[str, str], float]:
        """
        Updates edge weights based on co-activation of metrics and mesh patterns.
        Returns a copy of the current edge weights.
        """
        for a, b in PAIRS:
            va = float(metrics.get(a, 0.0))
            vb = float(metrics.get(b, 0.0))
            co = (va - 0.5) * (vb - 0.5)

            base_a = _metric_base(a)
            base_b = _metric_base(b)
            pattern_a = float(mesh.get(f"{base_a}_pattern", 0.0))
            pattern_b = float(mesh.get(f"{base_b}_pattern", 0.0))
            modulation = 0.5 * (pattern_a + pattern_b)

            delta = self.lr * co * (1.0 + modulation)
            key = tuple(sorted((a, b)))
            current = self.edges.get(key, 0.0)
            self.edges[key] = _clamp(current + delta)

        return dict(self.edges)

    def apply(self, metrics: Dict[str, float]) -> Dict[str, float]:
        """
        Applies topological influence to metrics using the current edge weights.
        """
        if not self.edges:
            return dict(metrics)

        out = dict(metrics)
        influence: Dict[str, float] = {k: 0.0 for k in metrics.keys()}

        for (a, b), weight in self.edges.items():
            va = float(metrics.get(a, 0.0))
            vb = float(metrics.get(b, 0.0))
            influence[a] += weight * (vb - 0.5)
            influence[b] += weight * (va - 0.5)

        for key, value in metrics.items():
            adjusted = float(value) + influence.get(key, 0.0)
            if adjusted < 0.0:
                adjusted = 0.0
            if adjusted > 1.0:
                adjusted = 1.0
            out[key] = adjusted

        return out
