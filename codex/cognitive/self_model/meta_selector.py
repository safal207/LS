from __future__ import annotations

from dataclasses import dataclass

from .affect import AffectiveLayer
from .model import SelfModel


@dataclass
class MetaSelector:
    def choose_strategy(self, self_model: SelfModel, affect: AffectiveLayer) -> str:
        if affect.recommend_mode() == "low_intensity":
            return "energy_saving"
        if self_model.fragmentation > 0.5:
            return "stability_first"
        if self_model.confidence < 0.3:
            return "confidence_recovery"
        return "balanced"
