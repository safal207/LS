from __future__ import annotations
from dataclasses import dataclass
from typing import Dict

@dataclass
class TemporalNode:
    id: str
    resonance: float = 1.0
    harmony_bonus: float = 0.0

class TemporalGraph:
    def __init__(self):
        self.nodes: Dict[str, TemporalNode] = {}

    def strengthen_strong_links(self, threshold: float = 0.75, boost: float = 0.15) -> int:
        """Увеличивает resonance узлов выше threshold на boost."""
        count = 0
        for node in self.nodes.values():
            if node.resonance > threshold:
                node.resonance = min(1.0, node.resonance + boost)
                count += 1
        return count

    def get_meritocratic_axis(self) -> TemporalNode | None:
        """Возвращает главный узел оси — с максимальным resonance + harmony."""
        if not self.nodes:
            return None
        return max(self.nodes.values(), key=lambda n: n.resonance * (1 + getattr(n, 'harmony_bonus', 0)))

    def align_to_axis(self, new_node: TemporalNode) -> float:
        """Выравнивает новую связь по оси. Возвращает синергию (0–1)."""
        axis = self.get_meritocratic_axis()
        if not axis:
            return 0.0
        synergy = min(1.0, new_node.resonance * 0.7 + (1 - abs(new_node.resonance - axis.resonance)) * 0.3)
        new_node.resonance = min(1.0, new_node.resonance + synergy * 0.1)  # лёгкое усиление
        return synergy
