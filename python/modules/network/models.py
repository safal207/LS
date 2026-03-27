from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional


@dataclass
class NetworkExecutionPlan:
    mode: str
    route_key: Optional[str]
    coalition_id: Optional[str]
    derived_module_id: Optional[str]
    memory_case_id: Optional[str]
    reason: str
    confidence: float
    selected_backend: Optional[str] = None
    graph_decision: Optional[dict[str, Any]] = None
    path_decision: Optional[dict[str, Any]] = None
    derived_module: Optional[dict[str, Any]] = None
    available_backends: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NetworkSnapshot:
    snapshot_id: str
    timestamp: str
    route_health: dict[str, Any]
    coalition_health: dict[str, Any]
    derived_module_health: dict[str, Any]
    adequacy_score: float
    latency_score: float
    drift_score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TrajectoryRecord:
    period: str
    previous_snapshot_id: str
    current_snapshot_id: str
    deltas: dict[str, Any]
    trend: str
    risks: list[str]
    opportunities: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FutureScenario:
    scenario_id: str
    title: str
    assumptions: list[str]
    expected_benefits: list[str]
    expected_risks: list[str]
    projected_adequacy: float
    projected_cost: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
