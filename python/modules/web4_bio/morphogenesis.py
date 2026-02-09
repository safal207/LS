from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class MorphogenesisPrinciples:
    description: str = "Structural evolution of the network"
    signals: Tuple[str, ...] = ("role_shift", "edge_strength", "topology_change")
