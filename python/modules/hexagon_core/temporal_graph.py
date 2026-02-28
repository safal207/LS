from __future__ import annotations
from dataclasses import dataclass
from typing import Dict

@dataclass
class TemporalNode:
    id: str
    resonance: float = 1.0

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
