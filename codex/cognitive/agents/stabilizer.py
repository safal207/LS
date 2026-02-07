from __future__ import annotations

from typing import Any, Dict

from .base import InnerAgent


class StabilizerAgent(InnerAgent):
    def process(self, frame: Dict[str, Any]) -> Dict[str, Any]:
        state = frame.get("system_state", "stable")
        if state in ("overload", "fragmented"):
            return {
                "agent": self.name,
                "recommendation": "reduce_load",
                "priority": 0.9,
            }
        return {
            "agent": self.name,
            "recommendation": "normal",
            "priority": 0.3,
        }
