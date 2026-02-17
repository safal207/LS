from __future__ import annotations

import bisect
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque


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
    _sorted_wait_times: list[float] = field(default_factory=list, init=False)
    _volatility_times: Deque[int] = field(default_factory=lambda: deque(maxlen=100), init=False)
    _priority_insert_times: Deque[int] = field(default_factory=lambda: deque(maxlen=100), init=False)

    def record_volatility_computation(self, time_ns: int) -> None:
        self._volatility_times.append(time_ns)
        self._metrics.volatility_computation_time_ns = time_ns

    def record_priority_queue_insert(self, time_ns: int) -> None:
        self._priority_insert_times.append(time_ns)
        self._metrics.priority_queue_insert_time_ns = time_ns

    def record_priority_queue_pop(self, time_ns: int) -> None:
        self._metrics.priority_queue_pop_time_ns = time_ns

    def record_failover_detection(self, time_ms: float) -> None:
        self._metrics.failover_detection_time_ms = time_ms

    def record_failover_recovery(self, time_sec: float) -> None:
        self._metrics.failover_recovery_time_sec = time_sec

    def record_adaptive_alpha_change(self) -> None:
        self._metrics.adaptive_alpha_changes += 1

    def record_priority_wait_time(self, time_ms: float) -> None:
        evicted: float | None = None
        if len(self._priority_wait_times) == self._priority_wait_times.maxlen:
            evicted = self._priority_wait_times[0]

        self._priority_wait_times.append(time_ms)
        bisect.insort(self._sorted_wait_times, time_ms)

        if evicted is not None:
            evicted_idx = bisect.bisect_left(self._sorted_wait_times, evicted)
            if evicted_idx < len(self._sorted_wait_times):
                self._sorted_wait_times.pop(evicted_idx)

        if self._sorted_wait_times:
            p99_index = int((len(self._sorted_wait_times) - 1) * 0.99)
            self._metrics.priority_queue_wait_time_p99_ms = self._sorted_wait_times[p99_index]

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

        if self._metrics.failover_detection_time_ms > 500:
            violations.append(
                {
                    "metric": "failover_detection_time_ms",
                    "value": self._metrics.failover_detection_time_ms,
                    "budget": 500,
                    "severity": "warning",
                }
            )

        if self._metrics.failover_recovery_time_sec > 30:
            violations.append(
                {
                    "metric": "failover_recovery_time_sec",
                    "value": self._metrics.failover_recovery_time_sec,
                    "budget": 30,
                    "severity": "critical",
                }
            )

        return violations
