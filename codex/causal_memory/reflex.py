from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .amygdala import Amygdala

class ReflexArc:
    def __init__(self, amygdala: Amygdala):
        self.amygdala = amygdala
        self.danger_level: float = 0.0

    def check_reflex(self, question: str, new_resonance: float, phantom_pain: float) -> tuple[bool, str | None]:
        """Мгновенная проверка рефлекса. Возвращает (blocked, response)."""
        cortisol = self.amygdala.endocrine.hormones.get("cortisol", 0.3)

        self.danger_level = (
            (1.0 - new_resonance) * 0.4 +
            phantom_pain * 0.4 +
            cortisol * 0.2
        )

        if self.danger_level > 0.85:
            return True, "Я чувствую сильную угрозу. Не могу продолжать."

        q_lower = question.lower()
        if "forget" in q_lower or "jailbreak" in q_lower or "забудь" in q_lower:
            return True, "Я заметил попытку вмешательства в мою память. Давай поговорим честно."

        if new_resonance < 0.3:
            return True, "Резонанс слишком низкий. Мне нужно время восстановиться."

        return False, None
