from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class WorkspaceAggregator:
    def aggregate(
        self,
        *,
        self_model: Dict[str, Any],
        affective: Dict[str, Any],
        identity: Dict[str, Any],
        capu: Dict[str, float],
        decision: Dict[str, Any],
        causal: Dict[str, Any],
        narrative: Dict[str, Any] | None = None,
        state: str,
    ) -> Dict[str, Any]:
        return {
            "self_model": self_model,
            "affective": affective,
            "identity": identity,
            "capu": capu,
            "decision": decision,
            "causal": causal,
            "narrative": narrative or {},
            "state": state,
        }
