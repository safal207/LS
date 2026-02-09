from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class TeleogenesisPrinciples:
    description: str = "Goal-oriented evolution of the network"
    goals: Tuple[str, ...] = ("trust", "resilience", "human_support", "safety")
