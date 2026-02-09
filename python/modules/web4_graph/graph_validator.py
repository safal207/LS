from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .edge import GraphEdge
from .node import GraphNode


@dataclass
class Graph:
    nodes: Dict[str, GraphNode]
    edges: List[GraphEdge]

    def validate(self) -> None:
        for edge in self.edges:
            if edge.source not in self.nodes or edge.target not in self.nodes:
                raise ValueError(f"Edge references unknown node: {edge.edge_id}")
