from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class GlobalFrame:
    thread_id: str
    task_type: str
    system_state: str
    self_model: Dict[str, Any]
    affective: Dict[str, Any]
    capu_features: Dict[str, float]
    decision: Dict[str, Any]
    memory_refs: Dict[str, str]
    timestamp: str
    identity: Dict[str, Any] = field(default_factory=dict)
    merit_scores: Dict[str, float] = field(default_factory=dict)
    narrative_refs: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
