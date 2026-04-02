# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from dataclasses import dataclass

from .amygdala import Amygdala, AmygdalaBlockError

logger = logging.getLogger(__name__)

AFFECT_KEYWORDS: dict[str, float] = {
    "страх": -0.8,
    "страшно": -0.8,
    "опас": -0.7,
    "угроз": -0.7,
    "давлен": -0.6,
    "боязн": -0.6,
    "опасность": -0.75,
    "риск": -0.6,
    "паника": -0.7,
    "теряем": -0.7,
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
    amygdala_state: float = 0.5
    amygdala_pressure: float = 0.5
    harmony_score: float = 0.5


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
        harmony_score: float = 0.5,
    ) -> CausalNode:
        affect = self._compute_affect(text) if current_layer.lower() == "consumer" else 0.0
        effective_resonance = self._effective_resonance(resonance, affect)
        normalized_axis = self._normalize_axis_position(axis_position)

        logger.info(
            "Transition %s → %s | text='%s...' | raw_res=%.3f | affect=%.3f | effective_res=%.3f | axis=%.3f",
            current_layer,
            target_layer,
            text[:80],
            resonance,
            affect,
            effective_resonance,
            normalized_axis,
        )

        decision = self.amygdala.allow_transition(
            new_resonance=effective_resonance,
            axis_position=normalized_axis,
            delta_axis=delta_axis,
            affect=affect,
            harmony_score=harmony_score,
        )
        if not decision.allowed and decision.reason is not None:
            msg = (
                f"Amygdala blocked transition from {current_layer} to {target_layer} on text: '{text[:80]}...' | "
                f"reason: {decision.reason.value} | resonance={effective_resonance:.3f} | affect={affect:.3f} | "
                f"delta_axis={delta_axis:.3f} | state={decision.state:.3f}"
            )
            if effective_resonance < 0.25:
                 msg = f"Amygdala: sharp resonance drop | {msg}"
            logger.warning(msg)
            raise AmygdalaBlockError(decision.reason, state=decision.state, pressure=decision.pressure)

        return CausalNode(
            layer=target_layer,
            axis_position=normalized_axis,
            resonance=effective_resonance,
            affect=affect,
            text=text,
            amygdala_state=decision.state,
            amygdala_pressure=decision.pressure,
            harmony_score=decision.harmony_score,
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
