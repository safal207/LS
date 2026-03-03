from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .amygdala import Amygdala

logger = logging.getLogger(__name__)

class Metabolism:
    def __init__(self, amygdala: Amygdala):
        self.amygdala = amygdala
        self.waste_bin: list[dict[str, Any]] = []  # "навоз" — старые узлы/рефлексии
        self.lessons: list[str] = []  # постоянные уроки из сна
        self.nutrient_pool: float = 0.0  # запас энергии от переработки

    def digest_old_reflections(self) -> float:
        """Перерабатывает старые silent_reflection в уроки. Возвращает полученную энергию."""
        energy = 0.0
        if hasattr(self.amygdala, "last_silent_reflection") and self.amygdala.last_silent_reflection:
            lesson = f"Урок из тишины: {self.amygdala.last_silent_reflection[:80]}..."
            self.waste_bin.append({"type": "reflection", "content": lesson})
            self.lessons.append(lesson)
            energy = 0.05  # Базовая энергия от осмысления
            self.nutrient_pool += energy
            logger.info(f"Reflections digested → nutrient +{energy:.2f} (current: {self.nutrient_pool:.2f})")
            # При глубокой переработке (сон) или когда AgentLoop решит, рефлексия очищается
            self.amygdala.last_silent_reflection = None
        return energy

    def compost_pruned_nodes(self, pruned_count: int) -> float:
        """Превращает pruned узлы в питание для роста. Возвращает полученную энергию."""
        energy = 0.0
        if pruned_count > 0:
            energy = pruned_count * 0.01
            self.nutrient_pool += energy
            self.waste_bin.append({"type": "pruned", "count": pruned_count})
            logger.info(f"Pruned {pruned_count} → nutrient +{energy:.2f} (current: {self.nutrient_pool:.2f})")
        return energy

    def feed_growth(self, energy: float | None = None) -> float:
        """Использует накопленное или переданное питание для усиления оси."""
        # Если энергия передана явно, используем её напрямую (для циклов консолидации)
        # Иначе берем из пула
        if energy is not None:
            boost = min(0.15, energy * 0.6) # Слегка другие коэффициенты для прямой энергии
        elif self.nutrient_pool > 0.1:
            boost = min(0.1, self.nutrient_pool * 0.5)
            self.nutrient_pool -= boost
        else:
            return 0.0

        old_state = self.amygdala.state
        self.amygdala.state = max(0.0, self.amygdala.state - boost)
        actual_boost = old_state - self.amygdala.state
        logger.info(f"Nutrient fed → state reduced by {actual_boost:.2f} (new state: {self.amygdala.state:.2f})")
        return actual_boost

    def to_dict(self) -> dict[str, Any]:
        return {
            "waste_bin": self.waste_bin[-20:], # Хarним только последние 20 записей
            "lessons": self.lessons[-50:],    # Храним только последние 50 уроков
            "nutrient_pool": round(self.nutrient_pool, 4)
        }

    def from_dict(self, data: dict[str, Any]):
        self.waste_bin = data.get("waste_bin", [])
        self.lessons = data.get("lessons", [])[-50:]
        self.nutrient_pool = float(data.get("nutrient_pool", 0.0))
