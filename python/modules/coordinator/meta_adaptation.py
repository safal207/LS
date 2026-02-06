from __future__ import annotations

from dataclasses import dataclass

from .adaptive_bias import AdaptiveBias
from .confidence_dynamics import ConfidenceDynamics


@dataclass
class MetaAdaptationState:
    """
    Phase 16 - Meta-Adaptation State
    Tracks simple aggregates for adaptation.
    """

    avg_trajectory_error: float = 0.0
    avg_confidence: float = 0.5
    updates: int = 0


class MetaAdaptationLayer:
    """
    Phase 16 - Meta-Adaptation
    Skeleton: adjusts ConfidenceDynamics and AdaptiveBias parameters
    based on simple aggregates of error and confidence.
    """

    def __init__(self) -> None:
        self.state = MetaAdaptationState()

    def update_metrics(self, trajectory_error: float | None, confidence: float | None) -> None:
        if trajectory_error is None and confidence is None:
            return

        self.state.updates += 1
        n = float(self.state.updates)

        if trajectory_error is not None:
            self.state.avg_trajectory_error += (float(trajectory_error) - self.state.avg_trajectory_error) / n

        if confidence is not None:
            self.state.avg_confidence += (float(confidence) - self.state.avg_confidence) / n

    def adapt_confidence_dynamics(self, dynamics: ConfidenceDynamics) -> None:
        """
        Skeleton rule:
        - If avg_trajectory_error is high -> slow down changes (lower max_delta).
        - If avg_confidence is too low -> slightly increase alpha (react faster).
        """
        if self.state.updates < 10:
            return

        if self.state.avg_trajectory_error > 0.5:
            dynamics.max_delta = max(0.05, dynamics.max_delta - 0.05)

        if self.state.avg_confidence < 0.4:
            dynamics.alpha = min(0.9, dynamics.alpha + 0.1)

    def adapt_adaptive_bias(self, bias: AdaptiveBias) -> None:
        """
        Skeleton: no-op for now.
        Placeholder for future tuning of bias strength.
        """
        _ = bias
