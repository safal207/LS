from __future__ import annotations

import time
import uuid
from collections import deque
import json
from typing import Any

from ls.memory.edge import MemoryEdge
from ls.memory.node import MemoryNode


class MemoryGraph:
    def __init__(self):
        self._nodes: dict[str, MemoryNode] = {}
        self._edges: list[MemoryEdge] = []
        self._adj: dict[str, list[MemoryEdge]] = {}
        self._type_index: dict[str, set[str]] = {}
        self._content_index: dict[str, dict[str, set[str]]] = {}
        self._token_index: dict[str, set[str]] = {}
        self._node_tokens: dict[str, set[str]] = {}

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
        previous = self._nodes.get(node.node_id)
        if previous is not None:
            self._deindex_node(previous)
        self._nodes[node.node_id] = node
        self._adj.setdefault(node.node_id, [])
        self._index_node(node)
        return node

    def add_edge(self, edge: MemoryEdge) -> None:
        if edge.source not in self._nodes or edge.target not in self._nodes:
            raise KeyError("Both edge endpoints must exist in graph")
        self._edges.append(edge)
        self._adj.setdefault(edge.source, []).append(edge)

    def get_node(self, node_id: str) -> MemoryNode | None:
        return self._nodes.get(node_id)

    def find_nodes(self, *, node_type: str | None = None, content_key: str | None = None, content_value: Any | None = None) -> list[MemoryNode]:
        candidate_ids: set[str] | None = None
        if node_type is not None:
            candidate_ids = set(self._type_index.get(node_type, set()))
        if content_key is not None and content_value is not None:
            encoded = self._encode_content_value(content_value)
            content_matches = self._content_index.get(content_key, {}).get(encoded, set())
            candidate_ids = set(content_matches) if candidate_ids is None else candidate_ids.intersection(content_matches)

        out: list[MemoryNode] = []
        for node in self._nodes.values():
            if candidate_ids is not None and node.node_id not in candidate_ids:
                continue
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
        if not q_tokens:
            return []
        candidate_ids: set[str] = set()
        for token in q_tokens:
            candidate_ids.update(self._token_index.get(token, set()))
        if not candidate_ids:
            return []
        scored: list[tuple[float, MemoryNode]] = []
        for node_id in candidate_ids:
            node = self._nodes.get(node_id)
            if node is None:
                continue
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
        self._type_index.clear()
        self._content_index.clear()
        self._token_index.clear()
        self._node_tokens.clear()

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

    @staticmethod
    def _encode_content_value(value: Any) -> str:
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, ensure_ascii=True, sort_keys=True, default=str)
        return str(value)

    def _index_node(self, node: MemoryNode) -> None:
        node_id = node.node_id
        self._type_index.setdefault(node.node_type, set()).add(node_id)

        for key, value in node.content.items():
            encoded = self._encode_content_value(value)
            by_value = self._content_index.setdefault(str(key), {})
            by_value.setdefault(encoded, set()).add(node_id)

        tokens = self._tokenize(self._node_text(node))
        self._node_tokens[node_id] = tokens
        for token in tokens:
            self._token_index.setdefault(token, set()).add(node_id)

    def _deindex_node(self, node: MemoryNode) -> None:
        node_id = node.node_id
        typed = self._type_index.get(node.node_type)
        if typed is not None:
            typed.discard(node_id)
            if not typed:
                self._type_index.pop(node.node_type, None)

        for key, value in node.content.items():
            encoded = self._encode_content_value(value)
            by_value = self._content_index.get(str(key))
            if by_value is None:
                continue
            bucket = by_value.get(encoded)
            if bucket is not None:
                bucket.discard(node_id)
                if not bucket:
                    by_value.pop(encoded, None)
            if not by_value:
                self._content_index.pop(str(key), None)

        for token in self._node_tokens.pop(node_id, set()):
            owners = self._token_index.get(token)
            if owners is None:
                continue
            owners.discard(node_id)
            if not owners:
                self._token_index.pop(token, None)
