from __future__ import annotations

from typing import Any

from ls.memory.memory_graph import MemoryGraph


class QueryEngine:
    """Convenience query layer for MemoryGraph."""

    def __init__(self, graph: MemoryGraph):
        self.graph = graph

    def semantic_search(self, query: str, limit: int = 5):
        return self.graph.semantic_search(query=query, limit=limit)

    def extract_reasoning_context(self, node_id: str, depth: int = 2) -> dict[str, Any]:
        return self.graph.extract_context(node_id=node_id, depth=depth)

    def reasoning_path(self, source: str, target: str) -> list[str]:
        return self.graph.find_path(source_id=source, target_id=target)
