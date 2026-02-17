from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
from typing import Callable, Deque


@dataclass
class GovernanceMetrics:
    regulator_volatility: float = 0.0
    regulator_alpha_current: float = 0.3
    regulator_adjustment_velocity: float = 0.0
    transport_failover_count: int = 0
    transport_error_rate: float = 0.0
    priority_queue_depth: int = 0
    priority_inversion_count: int = 0


class AdaptiveGovernor:
    """Динамическая настройка параметров регулятора на основе волатильности."""

    def __init__(
        self,
        alpha_min: float = 0.2,
        alpha_max: float = 0.5,
        volatility_window: int = 100,
    ) -> None:
        self.alpha_min = alpha_min
        self.alpha_max = alpha_max
        self._throughput_history: Deque[float] = deque(maxlen=volatility_window)
        self._prev_alpha = 0.3

    def compute_adaptive_alpha(self, current_throughput: float) -> float:
        self._throughput_history.append(current_throughput)

        if len(self._throughput_history) < 10:
            return 0.3

        volatility = self._compute_volatility()

        if volatility > 0.5:
            alpha = self.alpha_max
        elif volatility < 0.2:
            alpha = self.alpha_min
        else:
            alpha = self.alpha_min + (volatility - 0.2) * (self.alpha_max - self.alpha_min) / 0.3

        self._prev_alpha = alpha
        return alpha

    def get_metrics(self) -> GovernanceMetrics:
        return GovernanceMetrics(
            regulator_volatility=self._compute_volatility(),
            regulator_alpha_current=self._prev_alpha,
            regulator_adjustment_velocity=0.0,
        )

    def _compute_volatility(self) -> float:
        if len(self._throughput_history) < 10:
            return 0.0
        mean = sum(self._throughput_history) / len(self._throughput_history)
        variance = sum((x - mean) ** 2 for x in self._throughput_history) / len(self._throughput_history)
        return math.sqrt(variance) / max(0.001, mean)


class AlertManager:
    """Пороговые алерты для метрик governance."""

    def __init__(self) -> None:
        self._alert_handlers: list[Callable[[list[dict[str, float | str]]], None]] = []
        self._thresholds = {
            "regulator_volatility": {"warning": 0.5, "critical": 0.8},
            "transport_failover_count": {"warning": 5, "critical": 20},
            "priority_queue_backlog": {"warning": 100, "critical": 500},
            "transport_error_rate": {"warning": 0.01, "critical": 0.05},
        }

    def register_alert_handler(self, handler: Callable[[list[dict[str, float | str]]], None]) -> None:
        self._alert_handlers.append(handler)

    def check_thresholds(self, metrics: GovernanceMetrics) -> list[dict[str, float | str]]:
        alerts: list[dict[str, float | str]] = []

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
