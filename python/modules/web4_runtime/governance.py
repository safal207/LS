from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque


@dataclass
class GovernanceMetrics:
    regulator_volatility: float = 0.0
    regulator_alpha_current: float = 0.3
    regulator_adjustment_velocity: float = 0.0
    transport_failover_count: int = 0
    transport_error_rate: float = 0.0
    priority_queue_depth: int = 0
    priority_inversion_count: int = 0


@dataclass
class AdaptiveGovernor:
    alpha_min: float = 0.2
    alpha_max: float = 0.5
    volatility_window: int = 100
    _window: Deque[float] = field(default_factory=deque, init=False)
    _alpha: float = field(default=0.3, init=False)
    _count: int = field(default=0, init=False)
    _mean: float = field(default=0.0, init=False)
    _m2: float = field(default=0.0, init=False)

    def compute_adaptive_alpha(self, current_throughput: float) -> float:
        self._count += 1
        delta = current_throughput - self._mean
        self._mean += delta / self._count
        delta2 = current_throughput - self._mean
        self._m2 += delta * delta2

        self._window.append(current_throughput)
        if len(self._window) > self.volatility_window:
            self._window.popleft()

        if self._count < 10:
            self._alpha = 0.3
            return self._alpha

        variance = max(0.0, self._m2 / self._count)
        volatility = math.sqrt(variance) / max(0.001, abs(self._mean))

        target_alpha = self.alpha_max - (volatility * (self.alpha_max - self.alpha_min))
        self._alpha = min(self.alpha_max, max(self.alpha_min, target_alpha))
        return self._alpha

    @property
    def alpha(self) -> float:
        return self._alpha

    def get_metrics(self) -> GovernanceMetrics:
        variance = max(0.0, self._m2 / self._count) if self._count else 0.0
        volatility = math.sqrt(variance) / max(0.001, abs(self._mean)) if self._count else 0.0
        return GovernanceMetrics(
            regulator_volatility=volatility,
            regulator_alpha_current=self._alpha,
            regulator_adjustment_velocity=0.0,
        )


class AlertManager:
    """Пороговые алерты для метрик governance."""

    def __init__(self) -> None:
        self._alert_handlers: list[Callable[[list[dict[str, Any]]], None]] = []
        self._thresholds: dict[str, dict[str, float]] = {
            "regulator_volatility": {"warning": 0.5, "critical": 0.8},
            "transport_failover_count": {"warning": 5, "critical": 20},
            "priority_queue_backlog": {"warning": 100, "critical": 500},
            "transport_error_rate": {"warning": 0.01, "critical": 0.05},
        }

    def register_alert_handler(self, handler: Callable[[list[dict[str, Any]]], None]) -> None:
        self._alert_handlers.append(handler)

    def check_thresholds(self, metrics: GovernanceMetrics) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []

        if metrics.regulator_volatility > self._thresholds["regulator_volatility"]["critical"]:
            alerts.append(
                {
                    "level": "critical",
                    "metric": "regulator_volatility",
                    "value": metrics.regulator_volatility,
                }
            )
        elif metrics.regulator_volatility > self._thresholds["regulator_volatility"]["warning"]:
            alerts.append(
                {
                    "level": "warning",
                    "metric": "regulator_volatility",
                    "value": metrics.regulator_volatility,
                }
            )

        for handler in self._alert_handlers:
            handler(alerts)

        return alerts
