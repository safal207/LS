from __future__ import annotations


def _clamp(value: float, low: float = -0.3, high: float = 0.3) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


class AdaptiveBias:
    """
    Phase 15 - Adaptive Coordinator Bias
    Computes soft decision bias from orientation and trajectory signals.
    Skeleton: linear combination with clamping.
    """

    def __init__(self) -> None:
        self.external_bias = 0.0

    def compute_orientation_bias(self, orientation: dict) -> float:
        tendency = float(orientation.get("tendency", 0.0))
        weight = float(orientation.get("weight", 0.0))
        return _clamp(0.5 * tendency + 0.5 * weight, low=-0.2, high=0.2)

    def compute_trajectory_bias(self, trajectory_error: float | None) -> float:
        if trajectory_error is None:
            return 0.0
        return _clamp(-float(trajectory_error) * 0.2, low=-0.2, high=0.2)

    def combine(self, orientation_bias: float, trajectory_bias: float) -> float:
        return _clamp(orientation_bias + trajectory_bias + self.external_bias)

    def apply_external_bias(self, delta: float) -> None:
        self.external_bias = _clamp(self.external_bias + float(delta), low=-0.2, high=0.2)
