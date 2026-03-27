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
