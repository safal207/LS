from __future__ import annotations

import time
import uuid
from collections import deque
from typing import Any

from ls.memory.edge import MemoryEdge
from ls.memory.node import MemoryNode


class MemoryGraph:
    def __init__(self):
        self._nodes: dict[str, MemoryNode] = {}
        self._edges: list[MemoryEdge] = []
        self._adj: dict[str, list[MemoryEdge]] = {}

    def add_node(self, node: MemoryNode | None = None, *, node_type: str | None = None, content: dict[str, Any] | None = None) -> MemoryNode:
        if node is None:
            if not node_type:
                raise ValueError("node_type is required when node is not provided")
            node = MemoryNode(
                node_id=f"{node_type}-{uuid.uuid4().hex[:10]}",
                node_type=node_type,
                content=content or {},
                timestamp=time.time(),
            )
        self._nodes[node.node_id] = node
        self._adj.setdefault(node.node_id, [])
        return node

    def add_edge(self, edge: MemoryEdge) -> None:
        if edge.source not in self._nodes or edge.target not in self._nodes:
            raise KeyError("Both edge endpoints must exist in graph")
        self._edges.append(edge)
        self._adj.setdefault(edge.source, []).append(edge)

    def get_node(self, node_id: str) -> MemoryNode | None:
        return self._nodes.get(node_id)

    def find_nodes(self, *, node_type: str | None = None, content_key: str | None = None, content_value: Any | None = None) -> list[MemoryNode]:
        # TODO: add internal indexes by node_type/content keys for large graphs.
        out: list[MemoryNode] = []
        for node in self._nodes.values():
            if node_type is not None and node.node_type != node_type:
                continue
            if content_key is not None and node.content.get(content_key) != content_value:
                continue
            out.append(node)
        return out

    def find_first_node(self, *, node_type: str | None = None, content_key: str | None = None, content_value: Any | None = None) -> MemoryNode | None:
        matches = self.find_nodes(node_type=node_type, content_key=content_key, content_value=content_value)
        return matches[0] if matches else None

    def get_neighbors(self, node_id: str, relation: str | None = None) -> list[MemoryNode]:
        out: list[MemoryNode] = []
        for edge in self._adj.get(node_id, []):
            if relation and edge.relation != relation:
                continue
            node = self._nodes.get(edge.target)
            if node is not None:
                out.append(node)
        return out

    def find_path(self, source_id: str, target_id: str) -> list[str]:
        if source_id == target_id and source_id in self._nodes:
            return [source_id]
        if source_id not in self._nodes or target_id not in self._nodes:
            return []

        queue = deque([(source_id, [source_id])])
        seen = {source_id}
        while queue:
            node_id, path = queue.popleft()
            for edge in self._adj.get(node_id, []):
                nxt = edge.target
                if nxt in seen:
                    continue
                new_path = path + [nxt]
                if nxt == target_id:
                    return new_path
                seen.add(nxt)
                queue.append((nxt, new_path))
        return []

    def semantic_search(self, query: str, limit: int = 5) -> list[MemoryNode]:
        q_tokens = self._tokenize(query)
        scored: list[tuple[float, MemoryNode]] = []
        for node in self._nodes.values():
            text = self._node_text(node)
            n_tokens = self._tokenize(text)
            if not n_tokens:
                continue
            overlap = len(q_tokens.intersection(n_tokens))
            score = overlap / max(len(q_tokens), 1)
            if score > 0:
                scored.append((score, node))

        scored.sort(key=lambda item: (item[0], item[1].timestamp), reverse=True)
        return [node for _, node in scored[:limit]]

    def extract_context(self, node_id: str, depth: int = 2) -> dict[str, Any]:
        if node_id not in self._nodes:
            return {"nodes": [], "edges": [], "summaries": {"error": "node_not_found"}}

        visited = {node_id}
        frontier = {node_id}
        edges: list[MemoryEdge] = []

        for _ in range(max(depth, 0)):
            next_frontier: set[str] = set()
            for nid in frontier:
                for edge in self._adj.get(nid, []):
                    edges.append(edge)
                    if edge.target not in visited:
                        visited.add(edge.target)
                        next_frontier.add(edge.target)
            frontier = next_frontier
            if not frontier:
                break

        nodes = [self._nodes[nid] for nid in visited]
        recent_reflections = [n.to_dict() for n in nodes if n.node_type == "reflection"]
        recent_reflections.sort(key=lambda n: n["timestamp"], reverse=True)

        return {
            "nodes": [n.to_dict() for n in sorted(nodes, key=lambda n: n.timestamp)],
            "edges": [e.to_dict() for e in edges],
            "summaries": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "recent_reflections": recent_reflections[:3],
            },
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [node.to_dict() for node in self._nodes.values()],
            "edges": [edge.to_dict() for edge in self._edges],
        }

    def load_dict(self, data: dict[str, Any]) -> None:
        self._nodes.clear()
        self._edges.clear()
        self._adj.clear()

        for raw_node in data.get("nodes", []):
            node = MemoryNode.from_dict(raw_node)
            self.add_node(node)

        for raw_edge in data.get("edges", []):
            edge = MemoryEdge.from_dict(raw_edge)
            if edge.source in self._nodes and edge.target in self._nodes:
                self.add_edge(edge)

    @property
    def nodes(self) -> dict[str, MemoryNode]:
        return dict(self._nodes)

    @property
    def edges(self) -> list[MemoryEdge]:
        return list(self._edges)

    @staticmethod
    def _node_text(node: MemoryNode) -> str:
        payload = " ".join(f"{k}:{v}" for k, v in node.content.items())
        return f"{node.node_type} {payload}".lower()

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {t.strip(".,!?;:()[]{}\"'").lower() for t in text.split() if t.strip()}
