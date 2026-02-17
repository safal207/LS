from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
    _priority_wait_times: list[float] = field(default_factory=list, init=False)

    def record_volatility_computation(self, time_ns: int) -> None:
        self._metrics.volatility_computation_time_ns = time_ns

    def record_priority_queue_insert(self, time_ns: int) -> None:
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
        self._priority_wait_times.append(time_ms)
        if len(self._priority_wait_times) > 1000:
            self._priority_wait_times.pop(0)
        sorted_times = sorted(self._priority_wait_times)
        p99_index = int(len(sorted_times) * 0.99)
        if p99_index >= len(sorted_times):
            p99_index = len(sorted_times) - 1
        self._metrics.priority_queue_wait_time_p99_ms = sorted_times[p99_index]

    def get_metrics(self) -> PerformanceMetrics:
        return self._metrics

    def check_budgets(self) -> list[dict[str, Any]]:
        violations: list[dict[str, Any]] = []

        if self._metrics.volatility_computation_time_ns > 5000:
            violations.append(
                {
                    "metric": "volatility_computation_time_ns",
                    "value": self._metrics.volatility_computation_time_ns,
                    "budget": 5000,
                    "severity": "critical",
                }
            )

        if self._metrics.priority_queue_insert_time_ns > 2000:
            violations.append(
                {
                    "metric": "priority_queue_insert_time_ns",
                    "value": self._metrics.priority_queue_insert_time_ns,
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
