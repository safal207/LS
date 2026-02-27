from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class BlockReason(str, Enum):
    LOW_RESONANCE = "low_resonance"
    OVERLOAD = "overload"
    THREAT = "threat"


class AmygdalaBlockError(RuntimeError):
    def __init__(
        self,
        reason: BlockReason,
        *,
        state: float | None = None,
        pressure: float | None = None,
        message: str | None = None,
    ) -> None:
        super().__init__(message or f"amygdala blocked transition: {reason.value}")
        self.reason = reason
        self.state = state
        self.pressure = pressure


@dataclass(frozen=True)
class AmygdalaDecision:
    allowed: bool
    reason: BlockReason | None = None
    state: float = 0.5
    pressure: float = 0.5


class Amygdala:
    def __init__(
        self,
        *,
        window_size: int = 50,
        threshold_low: float = 0.4,
        threshold_overload: float = 0.7,
        max_axis_delta: float = 0.3,
        threat_affect: float = -0.5,
        smoothing: float = 0.35,
        hysteresis: float = 0.08,
        close_threshold: float = 0.65,
        adaptation_rate: float = 0.05,
    ) -> None:
        self._recent_resonance: deque[float] = deque(maxlen=window_size)
        self.history: deque[dict[str, Any]] = deque(maxlen=window_size)
        self.threshold_low = threshold_low
        self.threshold_overload = threshold_overload
        self.max_axis_delta = max_axis_delta
        self.threat_affect = threat_affect
        self.smoothing = max(0.05, min(0.95, smoothing))
        self.hysteresis = max(0.0, min(0.3, hysteresis))
        self.close_threshold = max(0.3, min(0.95, close_threshold))
        self.adaptation_rate = max(0.001, min(0.2, adaptation_rate))
        self.state = 0.5
        self.adaptive_bias = 0.0

    def evaluate(
        self,
        *,
        new_resonance: float,
        axis_position: float,
        delta_axis: float,
        affect: float,
    ) -> AmygdalaDecision:
        self._recent_resonance.append(new_resonance)
        pressure, reason = self._calculate_pressure(
            new_resonance=new_resonance,
            axis_position=axis_position,
            delta_axis=delta_axis,
            affect=affect,
        )

        target_state = max(0.0, min(1.0, pressure + self.adaptive_bias))
        if abs(target_state - self.state) > self.hysteresis:
            self.state = max(
                0.0,
                min(1.0, (self.smoothing * target_state) + ((1.0 - self.smoothing) * self.state)),
            )

        # Temporal centering force keeps the regulator around harmony midpoint.
        self.state = max(0.0, min(1.0, self.state + ((0.5 - self.state) * self.adaptation_rate * 0.08)))

        allowed = self.state < self.close_threshold
        if not allowed and reason is None:
            reason = BlockReason.OVERLOAD

        history_record = {
            "ts": time.time(),
            "state": self.state,
            "affect": affect,
            "resonance": new_resonance,
            "axis_position": axis_position,
            "delta_axis": delta_axis,
            "pressure": pressure,
            "decision": "allow" if allowed else "block",
            "outcome": "success" if allowed else "blocked",
            "reason": reason.value if reason is not None else None,
        }
        self.history.append(history_record)
        self._adapt_parameters()

        return AmygdalaDecision(
            allowed=allowed,
            reason=reason if not allowed else None,
            state=self.state,
            pressure=pressure,
        )

    def allow_transition(
        self,
        *,
        new_resonance: float,
        axis_position: float,
        delta_axis: float,
        affect: float,
    ) -> AmygdalaDecision:
        # Backward-compatible API
        return self.evaluate(
            new_resonance=new_resonance,
            axis_position=axis_position,
            delta_axis=delta_axis,
            affect=affect,
        )

    def learn_from_outcome(self, *, stable_interaction: bool, user_engaged: bool = True) -> None:
        reward = 0.0
        if stable_interaction and user_engaged:
            reward = -0.6 * self.adaptation_rate
        elif not stable_interaction:
            reward = 0.8 * self.adaptation_rate
        elif stable_interaction and not user_engaged:
            reward = 0.25 * self.adaptation_rate

        self.adaptive_bias = max(-0.2, min(0.2, self.adaptive_bias + reward))

    def _adapt_parameters(self) -> None:
        if len(self.history) < 10:
            return

        recent = list(self.history)[-10:]
        states = [float(item["state"]) for item in recent]
        blocked_ratio = sum(1 for item in recent if item["decision"] == "block") / len(recent)
        threat_ratio = sum(1 for item in recent if item.get("reason") == BlockReason.THREAT.value) / len(recent)
        avg_state = sum(states) / len(states)
        volatility = sum(abs(states[i] - states[i - 1]) for i in range(1, len(states))) / max(len(states) - 1, 1)

        # Centroorientation: softly pull behavior toward balanced median state.
        center_error = 0.5 - avg_state
        self.adaptive_bias = max(-0.2, min(0.2, self.adaptive_bias + (center_error * self.adaptation_rate * 0.3)))

        # If system is jittery, make transitions less reactive.
        if volatility > 0.18:
            self.smoothing = max(0.1, self.smoothing - (self.adaptation_rate * 0.2))

        # Frequent threat blocking means affect-gate is too strict: soften slightly.
        if blocked_ratio > 0.5 and threat_ratio > 0.25:
            self.threat_affect = max(-0.95, self.threat_affect - (self.adaptation_rate * 0.4))

        # Frequent overload blocks: close earlier and keep calmer response dynamics.
        if blocked_ratio > 0.55 and threat_ratio < 0.2:
            self.close_threshold = max(0.55, self.close_threshold - (self.adaptation_rate * 0.25))
            self.smoothing = max(0.1, self.smoothing - (self.adaptation_rate * 0.1))

        # Almost never blocks and avg too open -> restore caution a bit.
        if blocked_ratio < 0.1 and avg_state < 0.35:
            self.close_threshold = min(0.75, self.close_threshold + (self.adaptation_rate * 0.15))

    def _calculate_pressure(
        self,
        *,
        new_resonance: float,
        axis_position: float,
        delta_axis: float,
        affect: float,
    ) -> tuple[float, BlockReason | None]:
        resonance_drop = 1.0 - max(0.0, min(1.0, new_resonance))
        low_resonance_pressure = max(0.0, (self.threshold_low - new_resonance) / max(self.threshold_low, 1e-6))
        affect_pressure = 0.0
        if affect < self.threat_affect:
            affect_pressure = min(1.0, (self.threat_affect - affect) / max(abs(self.threat_affect), 1e-6))

        axis_pressure = 0.0
        if axis_position > self.threshold_overload:
            axis_pressure = min(1.0, (axis_position - self.threshold_overload) / max(1.0 - self.threshold_overload, 1e-6))

        delta_pressure = 0.0
        if delta_axis > self.max_axis_delta:
            delta_pressure = min(1.0, (delta_axis - self.max_axis_delta) / max(1.0 - self.max_axis_delta, 1e-6))

        pressure = (
            resonance_drop * 0.3
            + low_resonance_pressure * 0.1
            + affect_pressure * 0.2
            + axis_pressure * 0.3
            + delta_pressure * 0.1
        )
        pressure = max(0.0, min(1.0, pressure))

        reasons = {
            BlockReason.LOW_RESONANCE: max(resonance_drop, low_resonance_pressure),
            BlockReason.THREAT: affect_pressure,
            BlockReason.OVERLOAD: max(axis_pressure, delta_pressure),
        }
        reason = max(reasons, key=reasons.get)
        if reasons[reason] <= 0:
            reason = None

        logger.debug(
            "Amygdala pressure=%.3f state=%.3f reason=%s resonance=%.3f affect=%.3f axis=%.3f delta=%.3f bias=%.3f",
            pressure,
            self.state,
            reason.value if reason else None,
            new_resonance,
            affect,
            axis_position,
            delta_axis,
            self.adaptive_bias,
        )
        return pressure, reason
