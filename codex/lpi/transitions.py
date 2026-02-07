from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from .state import StateSnapshot, SystemState


class StateTransitionEngine:
    def __init__(self) -> None:
        self.current = StateSnapshot(
            state=SystemState.STABLE,
            context={},
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def update(
        self,
        *,
        capu_features: Dict[str, Any],
        metrics: Dict[str, Any],
        hardware: Dict[str, Any],
    ) -> StateSnapshot:
        new_state = self._infer_state(capu_features, metrics, hardware)
        snapshot = StateSnapshot(
            state=new_state,
            context={
                "capu": dict(capu_features),
                "metrics": dict(metrics),
                "hardware": dict(hardware),
            },
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self.current = snapshot
        return snapshot

    def _infer_state(
        self,
        capu: Dict[str, Any],
        metrics: Dict[str, Any],
        hardware: Dict[str, Any],
    ) -> SystemState:
        if metrics.get("realtimefactor", 0) > 1.0 or capu.get("rtf_estimate", 0) > 1.0:
            return SystemState.OVERLOAD

        if capu.get("logits_confidence_margin", 1.0) < 0.1:
            return SystemState.UNCERTAIN

        if capu.get("avg_attention_entropy", 0.0) > 5.0:
            return SystemState.DIFFUSE_FOCUS

        if capu.get("segments_count", 0) > 25:
            return SystemState.FRAGMENTED

        return SystemState.STABLE
