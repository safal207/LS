from __future__ import annotations

from dataclasses import dataclass

from .model import SelfModel


@dataclass
class AffectiveLayer:
    energy: float = 1.0
    tension: float = 0.0
    fatigue: float = 0.0

    def update(self, self_model: SelfModel) -> None:
        self.energy -= self_model.load * 0.1
        self.tension += self_model.fragmentation * 0.1
        self.fatigue += (1 - self_model.stability) * 0.05

        self._clamp()

    def recommend_mode(self) -> str:
        if self.energy < 0.3 or self.fatigue > 0.7:
            return "low_intensity"
        if self.tension > 0.5:
            return "safe_mode"
        return "normal"

    def _clamp(self) -> None:
        self.energy = max(0, min(1, self.energy))
        self.tension = max(0, min(1, self.tension))
        self.fatigue = max(0, min(1, self.fatigue))
