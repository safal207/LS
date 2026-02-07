from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class GlobalFrame:
    thread_id: str
    task_type: str
    system_state: str
    self_model: Dict[str, Any]
    affective: Dict[str, Any]
    identity: Dict[str, Any]
    capu_features: Dict[str, float]
    decision: Dict[str, Any]
    causal_context: Dict[str, Any]
    merit_scores: Dict[str, float]
    timestamp: str
