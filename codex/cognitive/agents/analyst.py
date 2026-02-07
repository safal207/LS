from __future__ import annotations

from typing import Any, Dict

from .base import InnerAgent


class AnalystAgent(InnerAgent):
    def process(self, frame: Dict[str, Any]) -> Dict[str, Any]:
        capu = frame.get("capu_features", {})
        decision = frame.get("decision", {})
        return {
            "agent": self.name,
            "insight": f"decision:{decision.get('choice', 'unknown')}",
            "confidence": capu.get("logits_confidence_margin", 0.5),
        }
