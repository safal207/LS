from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldNodeState:
    node_id: str
    timestamp: float
    orientation: dict[str, float]
    confidence: dict[str, float]
    trajectory: dict[str, float]


@dataclass(frozen=True)
class FieldState:
    nodes: dict[str, FieldNodeState]
    metrics: dict[str, float] | None = None
