from __future__ import annotations

from typing import Any, Dict

from .base import InnerAgent


class PredictorAgent(InnerAgent):
    def process(self, frame: Dict[str, Any]) -> Dict[str, Any]:
        self_model = frame.get("self_model", {})
        frag = self_model.get("fragmentation", 0.0)
        if frag > 0.5:
            next_state = "fragmented"
        elif frag > 0.3:
            next_state = "overload"
        else:
            next_state = "stable"
        return {
            "agent": self.name,
            "predicted_state": next_state,
        }
