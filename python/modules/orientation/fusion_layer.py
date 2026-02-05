from __future__ import annotations

from .metrics import OrientationSignals, clamp


class OrientationFusionLayer:
    """
    Phase 13.3 - Fusion Layer

    Combines raw organ signals into a unified, smoothed state vector.
    Skeleton: no side effects beyond in-memory smoothing.
    """

    def __init__(self, *, smoothing: float = 0.2) -> None:
        self.smoothing = smoothing
        self._prev: OrientationSignals | None = None

    def fuse(self, signals: OrientationSignals) -> OrientationSignals:
        if self._prev is None:
            self._prev = signals
            return signals

        alpha = clamp(self.smoothing, 0.0, 1.0)
        fused = OrientationSignals(
            diversity_score=self._blend(self._prev.diversity_score, signals.diversity_score, alpha),
            stability_score=self._blend(self._prev.stability_score, signals.stability_score, alpha),
            contradiction_rate=self._blend(self._prev.contradiction_rate, signals.contradiction_rate, alpha),
            drift_pressure=self._blend(self._prev.drift_pressure, signals.drift_pressure, alpha),
            confidence_budget=self._blend(self._prev.confidence_budget, signals.confidence_budget, alpha),
        )

        self._prev = fused
        return fused

    @staticmethod
    def _blend(previous: float, current: float, alpha: float) -> float:
        return clamp((alpha * previous) + ((1.0 - alpha) * current))
