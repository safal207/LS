from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MemoryNode:
    node_id: str
    node_type: str
    content: dict[str, Any]
    timestamp: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "content": self.content,
            "timestamp": self.timestamp,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "MemoryNode":
        return MemoryNode(
            node_id=str(data["node_id"]),
            node_type=str(data["node_type"]),
            content=dict(data.get("content", {})),
            timestamp=float(data["timestamp"]),
        )
