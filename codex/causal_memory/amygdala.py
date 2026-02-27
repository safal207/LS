from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class BlockReason(str, Enum):
    LOW_RESONANCE = "low_resonance"
    OVERLOAD = "overload"
    THREAT = "threat"


class AmygdalaBlockError(RuntimeError):
    def __init__(self, reason: BlockReason, message: str | None = None) -> None:
        super().__init__(message or f"amygdala blocked transition: {reason.value}")
        self.reason = reason


@dataclass(frozen=True)
class AmygdalaDecision:
    allowed: bool
    reason: BlockReason | None = None


class Amygdala:
    def __init__(
        self,
        *,
        window_size: int = 5,
        threshold_low: float = 0.4,
        threshold_overload: float = 0.7,
        threshold_delta_res: float = -0.4,
        max_axis_delta: float = 0.3,
        threat_affect: float = -0.5,
    ) -> None:
        self._recent_resonance: deque[float] = deque(maxlen=window_size)
        self.threshold_low = threshold_low
        self.threshold_overload = threshold_overload
        self.threshold_delta_res = threshold_delta_res
        self.max_axis_delta = max_axis_delta
        self.threat_affect = threat_affect

    def allow_transition(
        self,
        *,
        new_resonance: float,
        axis_position: float,
        delta_axis: float,
        affect: float,
    ) -> AmygdalaDecision:
        self._recent_resonance.append(new_resonance)
        if len(self._recent_resonance) > 1:
            delta_res = self._recent_resonance[-1] - self._recent_resonance[-2]
            if delta_res < self.threshold_delta_res:
                logger.warning("Amygdala blocked transition due to sharp resonance drop: %.3f", delta_res)
                return AmygdalaDecision(False, BlockReason.LOW_RESONANCE)

        avg_resonance = sum(self._recent_resonance) / len(self._recent_resonance)

        if affect < self.threat_affect:
            logger.warning("Amygdala blocked transition due to affect threat: %.3f", affect)
            return AmygdalaDecision(False, BlockReason.THREAT)

        if avg_resonance < self.threshold_low:
            logger.warning("Amygdala blocked transition due to low resonance average: %.3f", avg_resonance)
            return AmygdalaDecision(False, BlockReason.LOW_RESONANCE)

        if axis_position > self.threshold_overload and delta_axis > self.max_axis_delta:
            logger.warning(
                "Amygdala blocked transition due to overload axis_position=%.3f delta_axis=%.3f",
                axis_position,
                delta_axis,
            )
            return AmygdalaDecision(False, BlockReason.OVERLOAD)

        return AmygdalaDecision(True)
