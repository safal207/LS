from __future__ import annotations
from dataclasses import dataclass
import threading
from typing import Dict

@dataclass
class TemporalNode:
    id: str
    resonance: float = 1.0
    harmony_bonus: float = 0.5

class TemporalGraph:
    def __init__(self):
        self.nodes: Dict[str, TemporalNode] = {}
        self._graph_lock = threading.Lock()

    def strengthen_strong_links(self, threshold: float = 0.75, boost: float = 0.15) -> int:
        """Увеличивает resonance узлов выше threshold на boost."""
        count = 0
        with self._graph_lock:
            nodes = list(self.nodes.values())
        for node in nodes:
            if node.resonance > threshold:
                node.resonance = min(1.0, node.resonance + boost)
                count += 1
        return count

    def prune_weak_nodes(self, threshold: float = 0.25, active_window: int = 100) -> int:
        """Удаляет узлы с resonance ниже threshold."""
        with self._graph_lock:
            snapshot = list(self.nodes.items())
        to_remove = [node_id for node_id, node in snapshot if node.resonance < threshold]
        with self._graph_lock:
            for node_id in to_remove:
                self.nodes.pop(node_id, None)
        return len(to_remove)

    def get_meritocratic_axis(self) -> TemporalNode | None:
        """Возвращает главный узел оси — с максимальным resonance + harmony."""
        with self._graph_lock:
            nodes = list(self.nodes.values())
        if not nodes:
            return None
        return max(nodes, key=lambda n: n.resonance * (1 + getattr(n, 'harmony_bonus', 0)))

    def align_to_axis(self, new_node: TemporalNode) -> float:
        """Выравнивает новую связь по оси. Возвращает синергию (0–1)."""
        axis = self.get_meritocratic_axis()
        if not axis:
            return 0.0
        synergy = min(1.0, new_node.resonance * 0.7 + (1 - abs(new_node.resonance - axis.resonance)) * 0.3)
        new_node.resonance = min(1.0, new_node.resonance + synergy * 0.1)  # лёгкое усиление
        return synergy
