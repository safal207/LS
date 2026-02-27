from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

"""
Теория струн как метафора регулятора:
Z-ось — причинность, T-ось — время, P-ось — частота привязанности/эмпатии.
Fuzzy-регулятор — резонатор, protection_level — демпфер.
"""


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
    protection_level: str = "mild_protection"
    protection_score: float = 0.5


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
        self.adaptation_rate = max(0.01, min(0.35, adaptation_rate))
        self.state = 0.5
        self.adaptive_bias = 0.0
        self.personality_p = 0.5
        self.protection_shift = 0.0

    def evaluate(
        self,
        *,
        new_resonance: float,
        axis_position: float,
        delta_axis: float,
        affect: float,
    ) -> AmygdalaDecision:
        self._recent_resonance.append(new_resonance)

        pressure, reason, protection_score, protection_level = self._calculate_pressure(
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

        if protection_score > 0.6:
            protection_floor = 0.55 + (((protection_score - 0.6) / 0.4) * 0.25)
            self.state = max(self.state, min(0.8, protection_floor))

        centering_force = self.adaptation_rate * (0.18 if protection_score > 0.6 else 0.10)
        self.state = max(0.0, min(1.0, self.state + ((0.5 - self.state) * centering_force)))

        allowed = protection_level in {"open", "mild_protection"}

        history_record = {
            "ts": time.time(),
            "state": self.state,
            "affect": affect,
            "resonance": new_resonance,
            "axis_position": axis_position,
            "delta_axis": delta_axis,
            "pressure": pressure,
            "protection_score": protection_score,
            "protection_level": protection_level,
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
            protection_level=protection_level,
            protection_score=protection_score,
        )

    def allow_transition(
        self,
        *,
        new_resonance: float,
        axis_position: float,
        delta_axis: float,
        affect: float,
    ) -> AmygdalaDecision:
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

        if stable_interaction and user_engaged:
            self.personality_p = min(1.0, self.personality_p + 0.015)
        elif not stable_interaction and user_engaged:
            self.personality_p = min(1.0, self.personality_p + 0.003)
        else:
            self.personality_p = max(0.0, self.personality_p - 0.01)

    def _adapt_parameters(self) -> None:
        if len(self.history) < 10:
            return

        recent = list(self.history)[-10:]
        states = [float(item["state"]) for item in recent]
        blocked_ratio = sum(1 for item in recent if item["decision"] == "block") / len(recent)
        threat_ratio = sum(1 for item in recent if item.get("reason") == BlockReason.THREAT.value) / len(recent)
        avg_state = sum(states) / len(states)
        volatility = sum(abs(states[i] - states[i - 1]) for i in range(1, len(states))) / max(len(states) - 1, 1)

        center_error = 0.5 - avg_state
        self.adaptive_bias = max(-0.2, min(0.2, self.adaptive_bias + (center_error * self.adaptation_rate * 0.3)))

        if volatility > 0.18:
            self.smoothing = max(0.1, self.smoothing - (self.adaptation_rate * 0.2))

        if blocked_ratio > 0.5 and threat_ratio > 0.25:
            self.threat_affect = max(-0.95, self.threat_affect - (self.adaptation_rate * 0.4))

        if blocked_ratio > 0.55 and threat_ratio < 0.2:
            self.smoothing = max(0.1, self.smoothing - (self.adaptation_rate * 0.1))

        if len(self.history) >= 20:
            if blocked_ratio > 0.6:
                self.protection_shift = max(-0.25, self.protection_shift - (self.adaptation_rate * 0.45))
            elif blocked_ratio < 0.15 and avg_state < 0.4:
                self.protection_shift = min(0.15, self.protection_shift + (self.adaptation_rate * 0.2))

    def _calculate_pressure(
        self,
        *,
        new_resonance: float,
        axis_position: float,
        delta_axis: float,
        affect: float,
    ) -> tuple[float, BlockReason | None, float, str]:
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

        empathy_relief = max(0.0, self.personality_p - 0.7)
        if empathy_relief > 0.0:
            pressure *= max(0.7, 1.0 - (0.3 * empathy_relief / 0.3))

        axis_overload = max(axis_pressure, delta_pressure)
        fuzzy_score = self._fuzzy_protection_level(
            resonance_drop=resonance_drop,
            affect=affect,
            axis_overload=axis_overload,
            base_pressure=pressure,
        )

        if axis_overload >= 0.55:
            fuzzy_score = max(fuzzy_score, 0.66)
        if affect <= -0.55:
            fuzzy_score = max(fuzzy_score, 0.62)
        if affect <= -0.85:
            fuzzy_score = max(fuzzy_score, 0.78)

        if empathy_relief > 0.0:
            fuzzy_score *= max(0.8, 1.0 - (0.2 * empathy_relief / 0.3))

        protection_level = self._label_protection_level(fuzzy_score)
        reason = None

        logger.debug(
            "Amygdala pressure=%.3f fuzzy=%.3f level=%s state=%.3f reason=%s p=%.3f",
            pressure,
            fuzzy_score,
            protection_level,
            self.state,
            reason.value if reason else None,
            self.personality_p,
        )
        return pressure, reason, fuzzy_score, protection_level

    def _fuzzy_protection_level(
        self,
        *,
        resonance_drop: float,
        affect: float,
        axis_overload: float,
        base_pressure: float,
    ) -> float:
        def tri(value: float, left: float, center: float, right: float) -> float:
            if value <= left or value >= right:
                return 0.0
            if value == center:
                return 1.0
            if value < center:
                return (value - left) / max(center - left, 1e-6)
            return (right - value) / max(right - center, 1e-6)

        def trap(value: float, left: float, left_top: float, right_top: float, right: float) -> float:
            if value <= left or value >= right:
                return 0.0
            if left_top <= value <= right_top:
                return 1.0
            if value < left_top:
                return (value - left) / max(left_top - left, 1e-6)
            return (right - value) / max(right - right_top, 1e-6)

        resonance_very_low = trap(resonance_drop, 0.0, 0.0, 0.15, 0.3)
        resonance_low = tri(resonance_drop, 0.1, 0.35, 0.55)
        resonance_medium = tri(resonance_drop, 0.35, 0.6, 0.82)
        resonance_high = trap(resonance_drop, 0.65, 0.8, 1.0, 1.0)

        affect_negative_strong = trap(affect, -1.0, -1.0, -0.75, -0.35)
        affect_negative_mild = tri(affect, -0.6, -0.25, 0.05)
        affect_neutral = tri(affect, -0.2, 0.0, 0.2)
        affect_positive = trap(affect, 0.0, 0.25, 1.0, 1.0)

        overload_low = trap(axis_overload, 0.0, 0.0, 0.25, 0.45)
        overload_medium = tri(axis_overload, 0.3, 0.55, 0.8)
        overload_high = trap(axis_overload, 0.65, 0.82, 1.0, 1.0)

        rules = [
            (min(resonance_high, affect_negative_strong), 0.98),
            (min(resonance_low, affect_positive), 0.08),
            (overload_high, 0.92),
            (min(resonance_medium, affect_neutral), 0.48),
            (resonance_high, 0.86),
            (min(affect_negative_strong, overload_medium), 0.9),
            (affect_negative_strong, 0.76),
            (min(resonance_very_low, affect_neutral, overload_low), 0.12),
            (min(affect_negative_mild, resonance_medium), 0.58),
            (min(resonance_low, overload_low), 0.32),
            (min(affect_neutral, resonance_medium, overload_low), 0.35),
        ]
        weighted_sum = sum(strength * output for strength, output in rules)
        strength_sum = sum(strength for strength, _ in rules)
        fuzzy_output = weighted_sum / max(strength_sum, 1e-6) if strength_sum > 0 else base_pressure

        blended = (0.75 * fuzzy_output) + (0.25 * base_pressure)
        centered = blended + ((self.state - 0.5) * 0.08)
        calibrated = centered + self.protection_shift
        return max(0.0, min(1.0, calibrated))

    @staticmethod
    def _label_protection_level(protection_score: float) -> str:
        if protection_score < 0.3:
            return "open"
        if protection_score < 0.62:
            return "mild_protection"
        if protection_score < 0.82:
            return "strong_protection"
        return "full_protection"
