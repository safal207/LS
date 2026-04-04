# -*- coding: utf-8 -*-
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

    def __post_init__(self) -> None:
        self._window = deque(maxlen=max(1, self.volatility_window))

    def compute_adaptive_alpha(self, current_throughput: float) -> float:
        self._window.append(current_throughput)

        if len(self._window) < 10:
            self._alpha = 0.3
            return self._alpha

        volatility = self._compute_window_volatility()

        high_volatility = 0.5
        low_volatility = 0.2
        if volatility > high_volatility:
            target_alpha = self.alpha_min
        elif volatility < low_volatility:
            target_alpha = self.alpha_max
        else:
            span = high_volatility - low_volatility
            fraction = (volatility - low_volatility) / span
            target_alpha = self.alpha_max - (fraction * (self.alpha_max - self.alpha_min))
        self._alpha = min(self.alpha_max, max(self.alpha_min, target_alpha))
        return self._alpha

    @property
    def alpha(self) -> float:
        return self._alpha

    def get_metrics(self) -> GovernanceMetrics:
        return GovernanceMetrics(
            regulator_volatility=self._compute_window_volatility(),
            regulator_alpha_current=self._alpha,
            regulator_adjustment_velocity=0.0,
        )

    def _compute_window_volatility(self) -> float:
        if len(self._window) < 10:
            return 0.0
        values = list(self._window)
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        return math.sqrt(variance) / max(0.001, abs(mean))


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
