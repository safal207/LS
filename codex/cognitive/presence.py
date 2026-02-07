from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class PresenceMonitor:
    current_state: str = "stable"
    history: list[str] = field(default_factory=lambda: ["stable"])

    def update(
        self,
        capu_features: Dict[str, float],
        metrics: Dict[str, Any],
        hardware: Dict[str, Any] | None = None,
    ) -> str:
        hardware = hardware or {}
        latency = metrics.get("latency_s") or metrics.get("latency_ms")
        rtf = capu_features.get("rtf_estimate")
        error = metrics.get("error")

        next_state = "stable"
        if error:
            next_state = "fragmented"
        elif isinstance(latency, (int, float)) and latency > 1.5:
            next_state = "overload"
        elif rtf is not None and rtf > 1.2:
            next_state = "overload"
        elif not capu_features:
            next_state = "uncertain"
        elif hardware.get("ram_gb") and hardware.get("ram_gb") < 4:
            next_state = "overload"

        self.current_state = next_state
        self.history.append(next_state)
        return next_state
