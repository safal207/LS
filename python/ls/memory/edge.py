from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MemoryEdge:
    source: str
    target: str
    relation: str
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "weight": self.weight,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "MemoryEdge":
        return MemoryEdge(
            source=str(data["source"]),
            target=str(data["target"]),
            relation=str(data["relation"]),
            weight=float(data.get("weight", 1.0)),
        )
