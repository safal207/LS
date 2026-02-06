from __future__ import annotations


def _clamp(value: float, low: float = -0.2, high: float = 0.2) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


class FieldBias:
    """
    Phase 17.2 - Field-Aware Bias
    Computes small bias signals from field resonance metrics.
    """

    def compute_bias(self, metrics: dict[str, float]) -> dict[str, float]:
        if not metrics:
            return {
                "orientation_bias": 0.0,
                "confidence_bias": 0.0,
                "trajectory_bias": 0.0,
            }

        coherence = float(metrics.get("orientation_coherence", 0.0))
        alignment = float(metrics.get("confidence_alignment", 0.0))
        tension = float(metrics.get("trajectory_tension", 0.0))

        orientation_bias = _clamp(-(1.0 - self._clamp01(coherence)))
        confidence_bias = _clamp(-(1.0 - self._clamp01(alignment)))
        trajectory_bias = _clamp(-self._clamp01(tension))

        return {
            "orientation_bias": orientation_bias,
            "confidence_bias": confidence_bias,
            "trajectory_bias": trajectory_bias,
        }

    @staticmethod
    def _clamp01(value: float) -> float:
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return value
