from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class TemporalNode:
    id: str
    resonance: float = 1.0


@dataclass
class TemporalGraph:
    nodes: Dict[str, TemporalNode] = field(default_factory=dict)
    active_chain: List[TemporalNode] = field(default_factory=list)

    def remove_node(self, node: TemporalNode) -> None:
        if node.id in self.nodes:
            del self.nodes[node.id]
        if node in self.active_chain:
            self.active_chain.remove(node)

    def prune_weak_nodes(self, threshold: float = 0.25, active_window: int = 100) -> int:
        """Удаляет узлы с resonance < threshold, если они не в последних active_window взаимодействиях."""
        to_remove = []
        protected = self.active_chain[-active_window:] if active_window > 0 else []
        for node in self.nodes.values():
            if node.resonance < threshold and node not in protected:
                to_remove.append(node)
        for node in to_remove:
            self.remove_node(node)
        # Re-index если нужно (для dict/list-based graph — rebuild index)
        return len(to_remove)
