from __future__ import annotations

from typing import Any, Dict

from .base import InnerAgent


class IntegratorAgent(InnerAgent):
    def process(self, frame: Dict[str, Any]) -> Dict[str, Any]:
        merit = frame.get("merit_scores", {})
        if not merit:
            integrated = 0.0
        else:
            integrated = sum(merit.values()) / len(merit)
        return {
            "agent": self.name,
            "integrated_merit": integrated,
        }
