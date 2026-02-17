from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque


class _P2QuantileEstimator:
    """Constant-space online quantile estimator (P² algorithm)."""

    def __init__(self, quantile: float) -> None:
        self.quantile = min(1.0, max(0.0, quantile))
        self._samples: list[float] = []
        self._q: list[float] = []
        self._n: list[int] = []
        self._np: list[float] = []
        self._dn = [0.0, self.quantile / 2.0, self.quantile, (1.0 + self.quantile) / 2.0, 1.0]

    def add(self, value: float) -> None:
        if len(self._samples) < 5:
            self._samples.append(value)
            if len(self._samples) == 5:
                self._samples.sort()
                self._q = self._samples.copy()
                self._n = [1, 2, 3, 4, 5]
                self._np = [1.0, 1.0 + 2.0 * self.quantile, 1.0 + 4.0 * self.quantile, 3.0 + 2.0 * self.quantile, 5.0]
            return

        if value < self._q[0]:
            self._q[0] = value
            k = 0
        elif value >= self._q[4]:
            self._q[4] = value
            k = 3
        else:
            k = 0
            for i in range(4):
                if self._q[i] <= value < self._q[i + 1]:
                    k = i
                    break

        for i in range(k + 1, 5):
            self._n[i] += 1
        for i in range(5):
            self._np[i] += self._dn[i]

        for i in range(1, 4):
            d = self._np[i] - self._n[i]
            if (d >= 1 and self._n[i + 1] - self._n[i] > 1) or (d <= -1 and self._n[i - 1] - self._n[i] < -1):
                sign = 1 if d > 0 else -1
                qn = self._parabolic(i, sign)
                if self._q[i - 1] < qn < self._q[i + 1]:
                    self._q[i] = qn
                else:
                    self._q[i] = self._linear(i, sign)
                self._n[i] += sign

    def value(self) -> float:
        if len(self._samples) < 5:
            if not self._samples:
                return 0.0
            ordered = sorted(self._samples)
            idx = int((len(ordered) - 1) * self.quantile)
            return ordered[idx]
        return self._q[2]

    def _parabolic(self, i: int, d: int) -> float:
        return self._q[i] + (d / (self._n[i + 1] - self._n[i - 1])) * (
            (self._n[i] - self._n[i - 1] + d) * (self._q[i + 1] - self._q[i]) / (self._n[i + 1] - self._n[i])
            + (self._n[i + 1] - self._n[i] - d) * (self._q[i] - self._q[i - 1]) / (self._n[i] - self._n[i - 1])
        )

    def _linear(self, i: int, d: int) -> float:
        return self._q[i] + d * (self._q[i + d] - self._q[i]) / (self._n[i + d] - self._n[i])


@dataclass
class PerformanceMetrics:
    volatility_computation_time_ns: int = 0
    priority_queue_insert_time_ns: int = 0
    priority_queue_pop_time_ns: int = 0
    failover_detection_time_ms: float = 0.0
    failover_recovery_time_sec: float = 0.0
    adaptive_alpha_changes: int = 0
    priority_queue_wait_time_p99_ms: float = 0.0


@dataclass
class MetricsCollector:
    _metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics, init=False)
    _priority_wait_times: Deque[float] = field(default_factory=lambda: deque(maxlen=1000), init=False)
    _p99_estimator: _P2QuantileEstimator = field(default_factory=lambda: _P2QuantileEstimator(0.99), init=False)
    _volatility_times: Deque[int] = field(default_factory=lambda: deque(maxlen=100), init=False)
    _priority_insert_times: Deque[int] = field(default_factory=lambda: deque(maxlen=100), init=False)
    _failover_detection_times: Deque[float] = field(default_factory=lambda: deque(maxlen=100), init=False)
    _failover_recovery_times: Deque[float] = field(default_factory=lambda: deque(maxlen=100), init=False)

    def record_volatility_computation(self, time_ns: int) -> None:
        self._volatility_times.append(time_ns)
        self._metrics.volatility_computation_time_ns = time_ns

    def record_priority_queue_insert(self, time_ns: int) -> None:
        self._priority_insert_times.append(time_ns)
        self._metrics.priority_queue_insert_time_ns = time_ns

    def record_priority_queue_pop(self, time_ns: int) -> None:
        self._metrics.priority_queue_pop_time_ns = time_ns

    def record_failover_detection(self, time_ms: float) -> None:
        self._failover_detection_times.append(time_ms)
        self._metrics.failover_detection_time_ms = time_ms

    def record_failover_recovery(self, time_sec: float) -> None:
        self._failover_recovery_times.append(time_sec)
        self._metrics.failover_recovery_time_sec = time_sec

    def record_adaptive_alpha_change(self) -> None:
        self._metrics.adaptive_alpha_changes += 1

    def record_priority_wait_time(self, time_ms: float) -> None:
        self._priority_wait_times.append(time_ms)
        self._p99_estimator.add(time_ms)
        self._metrics.priority_queue_wait_time_p99_ms = self._p99_estimator.value()

    def get_metrics(self) -> PerformanceMetrics:
        return self._metrics

    def check_budgets(self) -> list[dict[str, Any]]:
        violations: list[dict[str, Any]] = []

        if self._volatility_times and max(self._volatility_times) > 5000:
            violations.append(
                {
                    "metric": "volatility_computation_time_ns",
                    "value": max(self._volatility_times),
                    "budget": 5000,
                    "severity": "critical",
                }
            )

        if self._priority_insert_times and max(self._priority_insert_times) > 2000:
            violations.append(
                {
                    "metric": "priority_queue_insert_time_ns",
                    "value": max(self._priority_insert_times),
                    "budget": 2000,
                    "severity": "critical",
                }
            )

        if self._failover_detection_times and max(self._failover_detection_times) > 500:
            violations.append(
                {
                    "metric": "failover_detection_time_ms",
                    "value": max(self._failover_detection_times),
                    "budget": 500,
                    "severity": "warning",
                }
            )

        if self._failover_recovery_times and max(self._failover_recovery_times) > 30:
            violations.append(
                {
                    "metric": "failover_recovery_time_sec",
                    "value": max(self._failover_recovery_times),
                    "budget": 30,
                    "severity": "critical",
                }
            )

        return violations
