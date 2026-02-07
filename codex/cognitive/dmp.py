from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class DMPRecord:
    decision: str
    alternatives: List[str]
    reasons: List[str]
    consequences: Dict[str, Any]
    context: Dict[str, Any]
    ltp_state: str | None
    presence_state: str | None
    lri_value: float | None
    kernel_signals: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "alternatives": list(self.alternatives),
            "reasons": list(self.reasons),
            "consequences": dict(self.consequences),
            "context": dict(self.context),
            "ltp_state": self.ltp_state,
            "presence_state": self.presence_state,
            "lri_value": self.lri_value,
            "kernel_signals": list(self.kernel_signals),
        }


@dataclass
class DMPProtocol:
    history: List[DMPRecord] = field(default_factory=list)

    def record(
        self,
        *,
        decision: str,
        alternatives: List[str],
        reasons: List[str],
        consequences: Dict[str, Any],
        context: Dict[str, Any],
    ) -> DMPRecord:
        ltp_state = context.get("ltp_state")
        presence_state = None
        lri_value = None
        kernel_signals: List[str] = []
        presence = context.get("presence", {}) if isinstance(context.get("presence", {}), dict) else {}
        lri = context.get("lri", {}) if isinstance(context.get("lri", {}), dict) else {}
        kernel = context.get("kernel", {}) if isinstance(context.get("kernel", {}), dict) else {}
        if isinstance(presence.get("state"), str):
            presence_state = presence.get("state")
        if isinstance(lri.get("value"), (int, float)):
            lri_value = float(lri.get("value"))
        signals = kernel.get("signals") if isinstance(kernel.get("signals"), list) else []
        kernel_signals = [signal for signal in signals if isinstance(signal, str)]
        record = DMPRecord(
            decision=decision,
            alternatives=list(alternatives),
            reasons=list(reasons),
            consequences=dict(consequences),
            context=dict(context),
            ltp_state=ltp_state if isinstance(ltp_state, str) else None,
            presence_state=presence_state,
            lri_value=lri_value,
            kernel_signals=kernel_signals,
        )
        self.history.append(record)
        return record
