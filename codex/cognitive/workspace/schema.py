from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class GlobalFrame:
    task_type: str
    thread_id: str
    system_state: str
    self_model: Dict[str, Any]
    affective: Dict[str, Any]
    identity: Dict[str, Any]
    capu_features: Dict[str, float]
    decision: Dict[str, Any]
    memory_refs: Dict[str, str]
    merit_scores: Dict[str, float]
    timestamp: str
    narrative_refs: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active_thread_id: str | None = None
    thread_priorities: Dict[str, float] = field(default_factory=dict)
    attention_distribution: Dict[str, float] = field(default_factory=dict)
