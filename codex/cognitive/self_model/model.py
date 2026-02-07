from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from codex.lpi import SystemState


@dataclass
class SelfModel:
    stability: float = 1.0
    confidence: float = 1.0
    load: float = 0.0
    fragmentation: float = 0.0
    preferred_modes: Dict[str, float] = field(default_factory=dict)

    def update_from_state(self, state: str) -> None:
        normalized = state.lower()
        if normalized == "overload":
            self.load += 0.2
            self.stability -= 0.1
        elif normalized == "uncertain":
            self.confidence -= 0.1
        elif normalized == "fragmented":
            self.fragmentation += 0.2
            self.stability -= 0.2
        elif normalized == "stable":
            self.stability += 0.05
            self.confidence += 0.05

        self._clamp()

    def update_from_lpi(self, state: SystemState | str) -> None:
        if isinstance(state, SystemState):
            mapped = {
                SystemState.OVERLOAD: "overload",
                SystemState.UNCERTAIN: "uncertain",
                SystemState.FRAGMENTED: "fragmented",
                SystemState.DIFFUSE_FOCUS: "fragmented",
                SystemState.STABLE: "stable",
            }.get(state)
            if mapped:
                self.update_from_state(mapped)
            return
        self.update_from_state(state)

    def update_from_capu(self, capu: Dict[str, float]) -> None:
        entropy = capu.get("avg_attention_entropy")
        margin = capu.get("logits_confidence_margin")
        rtf = capu.get("rtf_estimate")

        if entropy and entropy > 5:
            self.fragmentation += 0.1
        if margin and margin < 0.1:
            self.confidence -= 0.1
        if rtf and rtf > 1.2:
            self.load += 0.2

        self._clamp()

    def predict_next_state(self) -> str:
        if self.load > 0.7:
            return "overload"
        if self.fragmentation > 0.5:
            return "fragmented"
        if self.confidence < 0.3:
            return "uncertain"
        return "stable"

    def _clamp(self) -> None:
        self.stability = max(0, min(1, self.stability))
        self.confidence = max(0, min(1, self.confidence))
        self.load = max(0, min(1, self.load))
        self.fragmentation = max(0, min(1, self.fragmentation))
