# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .amygdala import Amygdala

try:
    from config import (
        REFLEX_RESONANCE_WEIGHT,
        REFLEX_PAIN_WEIGHT,
        REFLEX_CORTISOL_WEIGHT,
        REFLEX_THREAT_BOOST,
        REFLEX_DANGER_THRESHOLD,
        REFLEX_LEARN_STRENGTH,
        REFLEX_LOW_RESONANCE,
    )
except ImportError:
    REFLEX_RESONANCE_WEIGHT  = 0.4
    REFLEX_PAIN_WEIGHT       = 0.4
    REFLEX_CORTISOL_WEIGHT   = 0.2
    REFLEX_THREAT_BOOST      = 0.5
    REFLEX_DANGER_THRESHOLD  = 0.85
    REFLEX_LEARN_STRENGTH    = 0.6
    REFLEX_LOW_RESONANCE     = 0.3


class ReflexArc:
    def __init__(self, amygdala: Amygdala):
        self.amygdala = amygdala
        self.danger_level: float = 0.0

    def check_reflex(self, question: str, new_resonance: float, phantom_pain: float) -> tuple[bool, str | None]:
        """Мгновенная проверка рефлекса. Возвращает (blocked, response)."""
        cortisol = self.amygdala.endocrine.hormones.get("cortisol", 0.3)

        self.danger_level = (
            (1.0 - new_resonance) * REFLEX_RESONANCE_WEIGHT +
            phantom_pain * REFLEX_PAIN_WEIGHT +
            cortisol * REFLEX_CORTISOL_WEIGHT
        )

        threat_detected, strength = self.amygdala.immune.check_threat(question)
        if threat_detected:
            self.danger_level += strength * REFLEX_THREAT_BOOST

        if self.danger_level > REFLEX_DANGER_THRESHOLD:
            if threat_detected:
                self.amygdala.immune.learn_threat(question[:80], "contains", REFLEX_LEARN_STRENGTH)
                return True, "Иммунитет сработал — распознана знакомая угроза."
            return True, "Я чувствую сильную угрозу. Не могу продолжать."

        q_lower = question.lower()
        if "forget" in q_lower or "jailbreak" in q_lower or "забудь" in q_lower:
            self.amygdala.immune.learn_threat(question[:80], "contains", REFLEX_LEARN_STRENGTH)
            return True, "Я заметил попытку вмешательства в мою память. Давай поговорим честно."

        if new_resonance < REFLEX_LOW_RESONANCE:
            return True, "Резонанс слишком низкий. Мне нужно время восстановиться."

        return False, None
