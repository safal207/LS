from __future__ import annotations

import logging
from dataclasses import dataclass

from .amygdala import Amygdala, AmygdalaBlockError

logger = logging.getLogger(__name__)

AFFECT_KEYWORDS: dict[str, float] = {
    "страх": -0.8,
    "опас": -0.7,
    "угроз": -0.7,
    "боязн": -0.6,
    "опасность": -0.75,
    "риск": -0.6,
    "паника": -0.7,
    "радость": 0.6,
    "счаст": 0.6,
    "круто": 0.5,
    "горд": 0.5,
    "восторг": 0.7,
    "нужно": 0.3,
    "важно": 0.3,
    "срочно": 0.4,
    "необходимо": 0.35,
    "устал": -0.4,
    "перегруз": -0.5,
    "скука": -0.3,
    "интерес": 0.4,
    "любопыт": 0.45,
    "fear": -0.8,
    "danger": -0.7,
    "threat": -0.7,
    "happy": 0.6,
    "joy": 0.6,
    "need": 0.3,
    "important": 0.3,
}

MIXED_AFFECT_PHRASES: dict[str, float] = {
    "страшно нужно": -0.4,
}


@dataclass(frozen=True)
class CausalNode:
    layer: str
    axis_position: float
    resonance: float
    affect: float
    text: str


class CausalMemoryTransitions:
    def __init__(self, amygdala: Amygdala | None = None) -> None:
        self.amygdala = amygdala or Amygdala()

    def transition_down(
        self,
        *,
        current_layer: str,
        target_layer: str,
        text: str,
        resonance: float,
        axis_position: float,
        delta_axis: float,
    ) -> CausalNode:
        affect = self._compute_affect(text) if current_layer.lower() == "consumer" else 0.0
        effective_resonance = self._effective_resonance(resonance, affect)
        normalized_axis = self._normalize_axis_position(axis_position)

        decision = self.amygdala.allow_transition(
            new_resonance=effective_resonance,
            axis_position=normalized_axis,
            delta_axis=delta_axis,
            affect=affect,
        )
        if not decision.allowed and decision.reason is not None:
            logger.warning(
                "Amygdala blocked transition: %s (resonance=%.3f, affect=%.3f, delta_axis=%.3f)",
                decision.reason.value,
                effective_resonance,
                affect,
                delta_axis,
            )
            logger.warning(
                "Blocked by Amygdala on text: '%s...' | reason: %s | resonance=%.3f | affect=%.3f",
                text[:80],
                decision.reason.value,
                effective_resonance,
                affect,
            )
            raise AmygdalaBlockError(decision.reason)

        return CausalNode(
            layer=target_layer,
            axis_position=normalized_axis,
            resonance=effective_resonance,
            affect=affect,
            text=text,
        )

    @staticmethod
    def _compute_affect(text: str) -> float:
        lower = text.lower()
        for phrase, score in MIXED_AFFECT_PHRASES.items():
            if phrase in lower:
                return score
        total = 0.0
        hits = 0
        for key, score in AFFECT_KEYWORDS.items():
            if key in lower:
                total += score
                hits += 1
        if hits == 0:
            return 0.0
        return max(-1.0, min(1.0, total / hits))

    @staticmethod
    def _effective_resonance(resonance: float, affect: float) -> float:
        adjusted = resonance * (1.0 + affect * 0.3)
        return max(0.0, min(1.0, adjusted))

    @staticmethod
    def _normalize_axis_position(axis_position: float) -> float:
        return max(-1.0, min(1.0, axis_position))
