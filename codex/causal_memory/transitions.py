from __future__ import annotations

from dataclasses import dataclass

from .amygdala import Amygdala, AmygdalaBlockError

AFFECT_KEYWORDS: dict[str, float] = {
    "страх": -0.8,
    "опас": -0.7,
    "угроз": -0.7,
    "радость": 0.6,
    "нужно": 0.3,
    "важно": 0.3,
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

        decision = self.amygdala.allow_transition(
            new_resonance=effective_resonance,
            axis_position=axis_position,
            delta_axis=delta_axis,
            affect=affect,
        )
        if not decision.allowed and decision.reason is not None:
            raise AmygdalaBlockError(decision.reason)

        return CausalNode(
            layer=target_layer,
            axis_position=axis_position,
            resonance=effective_resonance,
            affect=affect,
            text=text,
        )

    @staticmethod
    def _compute_affect(text: str) -> float:
        lower = text.lower()
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
