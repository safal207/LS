from __future__ import annotations

import logging
import time
from pathlib import Path
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .memory_service import MemoryService

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




class VisceralMemory:
    """Висцеральная память — слой телесных сигналов перегрузки и разрешения."""

    def __init__(self, *, history_size: int = 20) -> None:
        self.phantom_pain: float = 0.0
        self.resolution_strength: float = 0.0
        self.last_trigger_intensity: float = 0.0
        self.history: deque[dict[str, float | str]] = deque(maxlen=history_size)

    def record_pain(self, intensity: float) -> None:
        self.phantom_pain = min(1.0, self.phantom_pain + intensity)
        self.last_trigger_intensity = max(0.0, intensity)
        self.history.append({"event": "pain", "intensity": self.last_trigger_intensity})

    def resolve(self, *, strength: float = 0.25) -> None:
        self.phantom_pain = max(0.0, self.phantom_pain - (strength * 1.2))
        self.resolution_strength = min(1.0, self.resolution_strength + strength)
        self.history.append({"event": "resolve", "strength": strength})

    @property
    def is_painful(self) -> bool:
        return self.phantom_pain > 0.3

    def get_influence(self) -> float:
        return min(1.0, (self.phantom_pain * 0.5) + (self.last_trigger_intensity * 0.3))


class Amygdala:
    def __init__(
        self,
        *,
        user_id: str = "default",
        memory_service: MemoryService | None = None,
        memory_dir: Path | None = None,
        persist_state: bool = False,
        window_size: int = 50,
        threshold_low: float = 0.4,
        threshold_overload: float = 0.7,
        max_axis_delta: float = 0.3,
        threat_affect: float = -0.5,
        smoothing: float = 0.35,
        hysteresis: float = 0.08,
        close_threshold: float = 0.65,
        adaptation_rate: float = 0.05,
        user_id: str = "default",
        memory_base_dir: str = "~/.ghostgpt/memory",
    ) -> None:
        self.user_id = user_id or "default"
        self.persist_state = persist_state
        self.memory_service = memory_service
        if self.persist_state and self.memory_service is None:
            self.memory_service = MemoryService(user_id=self.user_id, base_dir=memory_dir)

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
        self.user_id = user_id
        self.memory_service = MemoryService(user_id=user_id, base_dir=memory_base_dir)
        self.visceral = VisceralMemory()
        loaded = self.memory_service.load()

        self.personality_p = float(loaded.get("personality_p", self.personality_p))
        visceral = loaded.get("visceral", {}) if isinstance(loaded.get("visceral", {}), dict) else {}
        self.visceral.phantom_pain = float(visceral.get("phantom_pain", 0.0))
        self.visceral.resolution_strength = float(visceral.get("resolution_strength", 0.0))
        self.visceral.last_trigger_intensity = float(visceral.get("last_trigger_intensity", 0.0))
        self.visceral.history = deque(visceral.get("history", []), maxlen=20)
        self.last_snapshot: dict[str, float | str] = {
            "state": self.state,
            "protection_level": "mild_protection",
            "protection_score": 0.5,
            "personality_p": self.personality_p,
            "phantom_pain": self.phantom_pain,
            "resolution_strength": self.visceral.resolution_strength,
            "trigger": "none",
        }
        if self.persist_state:
            self._load_state()

    @property
    def phantom_pain(self) -> float:
        """Уровень фантомной боли / перегрузки из висцеральной памяти"""
        return self.visceral.phantom_pain

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

        if protection_score > 0.65 and affect < -0.4:
            trigger_intensity = max(abs(affect), abs(delta_axis))
            self.visceral.record_pain(min(0.25, trigger_intensity))

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

        trigger_parts: list[str] = []
        if delta_axis > self.max_axis_delta or axis_position > self.threshold_overload:
            trigger_parts.append("overload")
        if affect < self.threat_affect:
            trigger_parts.append("threat")
        if new_resonance < self.threshold_low:
            trigger_parts.append("low_resonance")
        trigger = " + ".join(trigger_parts) if trigger_parts else "none"

        self.last_snapshot = {
            "state": self.state,
            "protection_level": protection_level,
            "protection_score": protection_score,
            "personality_p": self.personality_p,
            "phantom_pain": self.phantom_pain,
            "resolution_strength": self.visceral.resolution_strength,
            "trigger": trigger,
        }

        self._adapt_parameters()
        self._persist_state()

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

        if stable_interaction:
            self.visceral.resolve(strength=0.25)

        self.last_snapshot.update(
            {
                "state": self.state,
                "personality_p": self.personality_p,
                "phantom_pain": self.phantom_pain,
                "resolution_strength": self.visceral.resolution_strength,
            }
        )
        self._persist_state()

    def _load_state(self) -> None:
        if not self.persist_state:
            return

        if self.memory_service is None:
            return

        payload = self.memory_service.load()
        if not payload:
            self._persist_state()
            return

        self.state = float(payload.get("state", self.state))
        self.adaptive_bias = float(payload.get("adaptive_bias", self.adaptive_bias))
        self.personality_p = float(payload.get("personality_p", self.personality_p))
        self.protection_shift = float(payload.get("protection_shift", self.protection_shift))
        self.visceral.phantom_pain = float(payload.get("phantom_pain", self.visceral.phantom_pain))
        self.visceral.resolution_strength = float(payload.get("resolution_strength", self.visceral.resolution_strength))
        self.visceral.last_trigger_intensity = float(
            payload.get("last_trigger_intensity", self.visceral.last_trigger_intensity)
        )
        self.last_snapshot.update(
            {
                "state": self.state,
                "personality_p": self.personality_p,
                "phantom_pain": self.phantom_pain,
                "resolution_strength": self.visceral.resolution_strength,
            }
        )

    def _persist_state(self) -> None:
        if not self.persist_state:
            return

        if self.memory_service is None:
            return

        self.memory_service.save(
            {
                "state": self.state,
                "adaptive_bias": self.adaptive_bias,
                "personality_p": self.personality_p,
                "protection_shift": self.protection_shift,
                "phantom_pain": self.visceral.phantom_pain,
                "resolution_strength": self.visceral.resolution_strength,
                "last_trigger_intensity": self.visceral.last_trigger_intensity,
            }
        )

        self.memory_service.save(
            {
                "user_id": self.user_id,
                "personality_p": self.personality_p,
                "visceral": {
                    "phantom_pain": self.visceral.phantom_pain,
                    "resolution_strength": self.visceral.resolution_strength,
                    "last_trigger_intensity": self.visceral.last_trigger_intensity,
                    "history": list(self.visceral.history),
                },
                "last_session": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        )

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

        visceral_influence = self.visceral.get_influence()
        if visceral_influence > 0.0:
            pressure = min(1.0, pressure + (0.15 * visceral_influence))
            fuzzy_score = min(1.0, fuzzy_score + (0.1 * visceral_influence))

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
