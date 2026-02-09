from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    kind: str
    address: str
    capabilities: Iterable[str] = field(default_factory=tuple)
    metadata: Dict[str, str] = field(default_factory=dict)
