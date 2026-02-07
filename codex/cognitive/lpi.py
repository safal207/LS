from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal


PresenceState = Literal["idle", "engaged", "focused", "diffuse", "overloaded", "liminal"]


@dataclass
class LPIState:
    state: PresenceState = "idle"
    confidence: float = 1.0

    def update(self, signals: Dict[str, Any]) -> None:
        lri = signals.get("lri", {}) if isinstance(signals.get("lri", {}), dict) else {}
        kernel = signals.get("kernel", {}) if isinstance(signals.get("kernel", {}), dict) else {}
        lri_value = lri.get("value")
        kernel_signals = kernel.get("signals") if isinstance(kernel.get("signals"), list) else []

        if "kernel_overload" in kernel_signals or (
            isinstance(lri_value, (int, float)) and lri_value >= 0.85
        ):
            self.state = "overloaded"
            self.confidence = 0.9
            return

        if isinstance(lri_value, (int, float)) and lri_value >= 0.6:
            self.state = "diffuse"
            self.confidence = 0.8
            return

        if isinstance(lri_value, (int, float)) and lri_value <= 0.3:
            self.state = "focused"
            self.confidence = 0.95
            return

        self.state = "engaged"
        self.confidence = 0.9
