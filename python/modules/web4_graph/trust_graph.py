from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict


class GraphTrustLevel(str, Enum):
    UNKNOWN = "unknown"
    PROBING = "probing"
    TRUSTED = "trusted"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class GraphTrustLink:
    node_id: str
    level: GraphTrustLevel
    reason: str


class GraphTrustFSM:
    def __init__(self) -> None:
        self._levels: Dict[str, GraphTrustLevel] = {}

    def get(self, node_id: str) -> GraphTrustLevel:
        return self._levels.get(node_id, GraphTrustLevel.UNKNOWN)

    def on_handshake(self, node_id: str) -> GraphTrustLink:
        level = GraphTrustLevel.PROBING if self.get(node_id) == GraphTrustLevel.UNKNOWN else self.get(node_id)
        self._levels[node_id] = level
        return GraphTrustLink(node_id, level, "handshake")

    def on_verified(self, node_id: str) -> GraphTrustLink:
        self._levels[node_id] = GraphTrustLevel.TRUSTED
        return GraphTrustLink(node_id, GraphTrustLevel.TRUSTED, "verified")

    def on_conflict(self, node_id: str) -> GraphTrustLink:
        current = self.get(node_id)
        if current == GraphTrustLevel.TRUSTED:
            self._levels[node_id] = GraphTrustLevel.PROBING
            return GraphTrustLink(node_id, GraphTrustLevel.PROBING, "conflict")
        self._levels[node_id] = GraphTrustLevel.BLOCKED
        return GraphTrustLink(node_id, GraphTrustLevel.BLOCKED, "conflict")

    def propagate(self, source: str, target: str) -> GraphTrustLink:
        if self.get(source) == GraphTrustLevel.TRUSTED:
            return self.on_handshake(target)
        return GraphTrustLink(target, self.get(target), "no_propagation")
