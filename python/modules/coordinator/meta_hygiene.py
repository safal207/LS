from __future__ import annotations

from dataclasses import dataclass

from .adaptive_bias import AdaptiveBias
from .confidence_dynamics import ConfidenceDynamics


@dataclass
class MetaHygieneState:
    """
    Phase 16.1 - Meta-Hygiene State
    Tracks last seen parameters and simple anomaly counters.
    """

    last_alpha: float = 0.5
    last_max_delta: float = 0.2
    alpha_spikes: int = 0
    delta_spikes: int = 0
    last_trajectory_error: float = 0.0


class MetaHygiene:
    """
    Phase 16.1 - Meta-Hygiene
    Stabilizes adaptation parameters to prevent runaway behavior.
    Skeleton: clamping + spike detection + baseline resets.
    """

    def __init__(
        self,
        *,
        alpha_bounds: tuple[float, float] = (0.1, 0.9),
        max_delta_bounds: tuple[float, float] = (0.05, 0.4),
        alpha_spike_threshold: float = 0.25,
        delta_spike_threshold: float = 0.2,
        spike_limit: int = 3,
        baseline_alpha: float = 0.5,
        baseline_max_delta: float = 0.2,
    ) -> None:
        self.alpha_bounds = alpha_bounds
        self.max_delta_bounds = max_delta_bounds
        self.alpha_spike_threshold = alpha_spike_threshold
        self.delta_spike_threshold = delta_spike_threshold
        self.spike_limit = spike_limit
        self.baseline_alpha = baseline_alpha
        self.baseline_max_delta = baseline_max_delta
        self.state = MetaHygieneState(
            last_alpha=baseline_alpha,
            last_max_delta=baseline_max_delta,
            last_trajectory_error=0.0,
        )

    def update(
        self,
        *,
        trajectory_error: float | None = None,
        confidence: float | None = None,
    ) -> None:
        """
        Track latest signals for anomaly detection.
        """
        if trajectory_error is not None:
            self.state.last_trajectory_error = float(trajectory_error)
        _ = confidence

    def correct_confidence_dynamics(self, dynamics: ConfidenceDynamics) -> None:
        """
        Clamp alpha/max_delta and reset on repeated spikes.
        """
        alpha = float(dynamics.alpha)
        max_delta = float(dynamics.max_delta)

        alpha_change = abs(alpha - self.state.last_alpha)
        delta_change = abs(max_delta - self.state.last_max_delta)

        if alpha_change > self.alpha_spike_threshold:
            self.state.alpha_spikes += 1
        if delta_change > self.delta_spike_threshold:
            self.state.delta_spikes += 1

        alpha = self._clamp(alpha, *self.alpha_bounds)
        max_delta = self._clamp(max_delta, *self.max_delta_bounds)

        if self.state.alpha_spikes >= self.spike_limit:
            alpha = self.baseline_alpha
            self.state.alpha_spikes = 0
        if self.state.delta_spikes >= self.spike_limit:
            max_delta = self.baseline_max_delta
            self.state.delta_spikes = 0

        dynamics.alpha = alpha
        dynamics.max_delta = max_delta

        self.state.last_alpha = alpha
        self.state.last_max_delta = max_delta

    def correct_adaptive_bias(self, bias: AdaptiveBias) -> None:
        """
        Skeleton: no-op for now, reserved for Phase 16.x.
        """
        _ = bias

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        if value < low:
            return low
        if value > high:
            return high
        return value
