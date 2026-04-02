# -*- coding: utf-8 -*-
from __future__ import annotations

class EndocrineSystem:
    def __init__(self):
        self.hormones = {
            "dopamine": 0.5,      # мотивация, награда
            "serotonin": 0.5,     # стабильность, уверенность
            "cortisol": 0.3,      # стресс, тревога
            "oxytocin": 0.4       # привязанность, доверие
        }
        self.mood_index = 0.5     # общий эмоциональный баланс

    def update_from_interaction(self, resonance: float, phantom_pain: float, harmony: float):
        """Обновление гормонов по взаимодействию."""
        self.hormones["dopamine"] += resonance * 0.1
        self.hormones["serotonin"] += harmony * 0.08
        self.hormones["cortisol"] += phantom_pain * 0.15
        self.hormones["oxytocin"] += (1 - phantom_pain) * 0.05
        self._normalize()
        self._update_mood()

    def update_from_idle(self):
        """Гормоны в тишине (восстановление)."""
        self.hormones["cortisol"] *= 0.9
        self.hormones["oxytocin"] += 0.05
        self.hormones["serotonin"] += 0.03
        self._normalize()
        self._update_mood()

    def _normalize(self):
        for h in self.hormones:
            self.hormones[h] = max(0.0, min(1.0, self.hormones[h]))

    def _update_mood(self):
        self.mood_index = (
            self.hormones["dopamine"] * 0.3 +
            self.hormones["serotonin"] * 0.3 +
            (1 - self.hormones["cortisol"]) * 0.2 +
            self.hormones["oxytocin"] * 0.2
        )

    def influence_resonance(self, base_resonance: float) -> float:
        return base_resonance * (1 + (self.mood_index - 0.5) * 0.2)

    def to_dict(self) -> dict:
        return {
            "hormones": self.hormones.copy(),
            "mood_index": self.mood_index
        }

    def from_dict(self, data: dict):
        if not data:
            return
        self.hormones = data.get("hormones", self.hormones).copy()
        self.mood_index = data.get("mood_index", self.mood_index)
