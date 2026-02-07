from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class TaskContext:
    task_type: str
    input_payload: Dict[str, Any]
    constraints: Dict[str, Any]
    candidates: List[str]


@dataclass
class DecisionContext:
    choice: str
    alternatives: List[str]
    reasons: List[str]


@dataclass
class LoopContext:
    task: TaskContext
    decision: DecisionContext
    model_output: Dict[str, Any]
    capu_features: Dict[str, float]
    metrics: Dict[str, Any]
    state_before: str
    state_after: str
    memory_record_id: str
    decision_record_id: str
    thread_id: str
    identity_snapshot: Dict[str, Any] = field(default_factory=dict)
