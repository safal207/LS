from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class MorphogenesisPrinciples:
    description: str = "Structural evolution of the network"
    signals: List[str] = ("role_shift", "edge_strength", "topology_change")
