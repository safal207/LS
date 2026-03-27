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
    need_profile: Optional[dict[str, Any]] = None
    goal_vector: Optional[dict[str, Any]] = None
    adequacy_report: Optional[dict[str, Any]] = None
    observer_report: Optional[dict[str, Any]] = None
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


@dataclass
class TuningFork:
    adequacy_target: float = 0.68
    latency_target: float = 0.55
    drift_ceiling: float = 0.35
    stale_module_limit: int = 1
    weak_route_limit: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AdequacyReport:
    status: str
    adequacy_gap: float
    latency_gap: float
    drift_gap: float
    route_dominance_risk: bool
    coalition_inflation_risk: bool
    module_drift_risk: bool
    risks: list[str]
    recommendations: list[str]
    observer_summary: dict[str, Any]
    tuning_fork: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ObserverReport:
    retrospective: dict[str, Any]
    trajectory: dict[str, Any]
    adequacy: dict[str, Any]
    status: str
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NeedProfile:
    urgency: float
    novelty: float
    uncertainty: float
    memory_gap: float
    compute_budget: float
    priority: str
    route_bias: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GoalVector:
    target_relevance: float
    target_thread_alignment: float
    target_hallucination_max: float
    target_latency_ms: float
    style: str
    strategy_bias: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
