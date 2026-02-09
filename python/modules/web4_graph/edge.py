from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class GraphEdge:
    edge_id: str
    source: str
    target: str
    relation: str
    weight: float = 1.0
    state: str = "active"
    metadata: Dict[str, str] = field(default_factory=dict)
