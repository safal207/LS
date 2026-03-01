from __future__ import annotations
from dataclasses import dataclass
from typing import Dict

@dataclass
class TemporalNode:
    id: str
    resonance: float = 1.0
    harmony_bonus: float = 0.5

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

    def prune_weak_nodes(self, threshold: float = 0.25, active_window: int = 100) -> int:
        """Удаляет узлы с resonance ниже threshold."""
        to_remove = [node_id for node_id, node in self.nodes.items() if node.resonance < threshold]
        for node_id in to_remove:
            del self.nodes[node_id]
        return len(to_remove)

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

    def select_best_offspring(self, offspring_ids: list[str]) -> str | None:
        """Выбирает лучшего потомка по resonance × (1 + harmony_bonus)."""
        best = None
        best_score = -1.0
        for oid in offspring_ids:
            node = self.nodes.get(oid, TemporalNode(id=oid))
            score = node.resonance * (1.0 + node.harmony_bonus)
            if score > best_score:
                best_score = score
                best = oid
        return best
