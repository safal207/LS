from __future__ import annotations

from typing import Iterable

from .state import FieldState


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


class FieldResonance:
    """
    Phase 17.1 - Field Resonance (Coherence Layer)
    Computes aggregate coherence metrics from a FieldState.
    """

    def compute(self, field_state: FieldState) -> dict[str, float]:
        nodes = list(field_state.nodes.values())
        if not nodes:
            return {
                "orientation_coherence": 0.0,
                "confidence_alignment": 0.0,
                "trajectory_tension": 0.0,
            }

        orientation_coherence = self._orientation_coherence(nodes)
        confidence_alignment = self._confidence_alignment(nodes)
        trajectory_tension = self._trajectory_tension(nodes)

        return {
            "orientation_coherence": orientation_coherence,
            "confidence_alignment": confidence_alignment,
            "trajectory_tension": trajectory_tension,
        }

    def _orientation_coherence(self, nodes: Iterable) -> float:
        node_list = list(nodes)
        if len(node_list) < 2:
            return 1.0

        distances: list[float] = []
        for i, a in enumerate(node_list):
            for b in node_list[i + 1 :]:
                distances.append(self._orientation_distance(a.orientation, b.orientation))
        avg_distance = sum(distances) / len(distances) if distances else 0.0
        return _clamp(1.0 - _clamp(avg_distance))

    def _confidence_alignment(self, nodes: Iterable) -> float:
        values = []
        for node in nodes:
            conf = node.confidence.get("smoothed")
            if conf is None:
                conf = node.confidence.get("raw")
            if conf is not None:
                values.append(float(conf))
        if len(values) < 2:
            return 1.0 if values else 0.0

        max_val = max(values)
        min_val = min(values)
        spread = _clamp(max_val - min_val)
        return _clamp(1.0 - spread)

    def _trajectory_tension(self, nodes: Iterable) -> float:
        values = []
        for node in nodes:
            err = node.trajectory.get("error")
            if err is not None:
                values.append(float(err))
        if len(values) < 2:
            return 0.0 if not values else _clamp(values[0])
        max_val = max(values)
        min_val = min(values)
        return _clamp(max_val - min_val)

    @staticmethod
    def _orientation_distance(a: dict[str, float], b: dict[str, float]) -> float:
        keys = set(a.keys()) | set(b.keys())
        if not keys:
            return 0.0
        diffs = [abs(float(a.get(k, 0.0)) - float(b.get(k, 0.0))) for k in keys]
        return sum(diffs) / len(diffs)
