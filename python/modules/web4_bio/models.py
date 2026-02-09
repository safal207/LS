from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class MorphogenesisModel:
    description: str = "Structural evolution model"
    signals: List[str] = field(default_factory=lambda: ["role_shift", "edge_strength", "topology_change"])


@dataclass(frozen=True)
class EpigenesisModel:
    description: str = "Behavioral adaptation model"
    signals: List[str] = field(default_factory=lambda: ["trust_transition", "routing_feedback", "observability"])


@dataclass(frozen=True)
class TeleogenesisModel:
    description: str = "Goal-oriented evolution model"
    goals: List[str] = field(default_factory=lambda: ["trust", "resilience", "human_support", "safety"])


@dataclass(frozen=True)
class BioAdaptiveNode:
    node_id: str
    morphogenesis: MorphogenesisModel = field(default_factory=MorphogenesisModel)
    epigenesis: EpigenesisModel = field(default_factory=EpigenesisModel)
    teleogenesis: TeleogenesisModel = field(default_factory=TeleogenesisModel)


@dataclass(frozen=True)
class BioAdaptiveEdge:
    edge_id: str
    morphogenesis: MorphogenesisModel = field(default_factory=MorphogenesisModel)
    epigenesis: EpigenesisModel = field(default_factory=EpigenesisModel)
