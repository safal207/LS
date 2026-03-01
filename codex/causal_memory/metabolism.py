from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .amygdala import Amygdala

logger = logging.getLogger(__name__)

class MetabolismEngine:
    def __init__(self, amygdala: Amygdala):
        self.amygdala = amygdala
        self.waste_bin: list[dict[str, Any]] = []  # "навоз" — старые узлы/рефлексии
        self.nutrient_pool: float = 0.0  # запас энергии от переработки

    def digest_old_reflections(self):
        """Перерабатывает старые silent_reflection в уроки."""
        if hasattr(self.amygdala, "last_silent_reflection") and self.amygdala.last_silent_reflection:
            lesson = f"Урок из тишины: {self.amygdala.last_silent_reflection[:80]}..."
            self.waste_bin.append({"type": "reflection", "content": lesson})
            self.nutrient_pool += 0.05  # энергия от осмысления
            logger.info(f"Reflections digested → nutrient +0.05 (current: {self.nutrient_pool:.2f})")
            # Мы не очищаем last_silent_reflection здесь, так как AgentLoop может захотеть её использовать
            # Но мы пометили её как переработанную в waste_bin

    def compost_pruned_nodes(self, pruned_count: int):
        """Превращает pruned узлы в питание для роста."""
        if pruned_count > 0:
            boost = pruned_count * 0.01
            self.nutrient_pool += boost
            self.waste_bin.append({"type": "pruned", "count": pruned_count})
            logger.info(f"Pruned {pruned_count} → nutrient +{boost:.2f} (current: {self.nutrient_pool:.2f})")

    def feed_growth(self) -> float:
        """Использует накопленное питание для усиления оси (снижения state/повышения resonance)."""
        if self.nutrient_pool > 0.1:
            # state в Amygdala: 0.0 - макс резонанс, 1.0 - макс блокировка
            # "Усиление" означает снижение state.
            boost = min(0.1, self.nutrient_pool * 0.5)
            old_state = self.amygdala.state
            self.amygdala.state = max(0.0, self.amygdala.state - boost)
            self.nutrient_pool -= boost
            actual_boost = old_state - self.amygdala.state
            logger.info(f"Nutrient fed → state reduced by {actual_boost:.2f} (new state: {self.amygdala.state:.2f})")
            return actual_boost
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "waste_bin": self.waste_bin[-20:], # Храним только последние 20 "уроков"
            "nutrient_pool": round(self.nutrient_pool, 4)
        }

    def from_dict(self, data: dict[str, Any]):
        self.waste_bin = data.get("waste_bin", [])
        self.nutrient_pool = float(data.get("nutrient_pool", 0.0))
