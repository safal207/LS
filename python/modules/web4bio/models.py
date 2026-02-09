from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class MorphogenesisModel:
    description: str = "Structural evolution model"
    signals: List[str] = ("role_shift", "edge_strength", "topology_change")


@dataclass(frozen=True)
class EpigenesisModel:
    description: str = "Behavioral adaptation model"
    signals: List[str] = ("trust_transition", "routing_feedback", "observability")


@dataclass(frozen=True)
class TeleogenesisModel:
    description: str = "Goal-oriented evolution model"
    goals: List[str] = ("trust", "resilience", "human_support", "safety")
