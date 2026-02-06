from __future__ import annotations


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


class ConfidenceDynamics:
    """
    Phase 15.1 - Confidence Dynamics
    Smooths and stabilizes decision confidence over time.
    Skeleton: exponential smoothing + max delta.
    """

    def __init__(self, alpha: float = 0.5, max_delta: float = 0.2) -> None:
        self.alpha = alpha
        self.max_delta = max_delta
        self._last_confidence: float | None = None

    def update(self, raw_confidence: float) -> float:
        raw_confidence = _clamp(float(raw_confidence))

        if self._last_confidence is None:
            self._last_confidence = raw_confidence
            return raw_confidence

        target = (self.alpha * raw_confidence) + ((1.0 - self.alpha) * self._last_confidence)

        delta = target - self._last_confidence
        if delta > self.max_delta:
            target = self._last_confidence + self.max_delta
        elif delta < -self.max_delta:
            target = self._last_confidence - self.max_delta

        self._last_confidence = _clamp(target)
        return self._last_confidence
