from __future__ import annotations

from copy import deepcopy
from typing import Any


class CognitiveIllusionDetector:
    """Detects weak reasoning patterns in beliefs and causal edges."""

    OVERCONFIDENCE_THRESHOLD = 0.8
    MIN_BELIEF_EVIDENCE = 4
    MIN_CAUSAL_EVIDENCE = 3

    def __init__(self, cognitive_state: dict[str, Any] | None):
        self.cognitive_state = cognitive_state or {}

    def _state(self) -> dict[str, Any]:
        raw = self.cognitive_state.get("state", self.cognitive_state)
        return raw if isinstance(raw, dict) else {}

    def _beliefs(self) -> list[dict[str, Any]]:
        beliefs = self._state().get("beliefs")
        if not isinstance(beliefs, list):
            return []
        return [belief for belief in beliefs if isinstance(belief, dict)]

    def _causal_edges(self) -> list[dict[str, Any]]:
        edges = self._state().get("causal_edges")
        if not isinstance(edges, list):
            return []
        return [edge for edge in edges if isinstance(edge, dict)]

    def detect_false_causation(self) -> list[dict[str, Any]]:
        """Identify causal edges with weak statistical evidence."""
        warnings: list[dict[str, Any]] = []
        for edge in self._causal_edges():
            confidence = float(edge.get("confidence", 0.0) or 0.0)
            evidence_count = int(edge.get("evidence_count", 0) or 0)
            if confidence >= 0.5 and evidence_count < self.MIN_CAUSAL_EVIDENCE:
                warnings.append(
                    {
                        "type": "false_causation",
                        "edge": f"{edge.get('cause', 'unknown')} → {edge.get('effect', 'unknown')}",
                        "message": "Possible correlation without sufficient support",
                    }
                )
        return warnings

    def detect_overconfidence(self) -> list[dict[str, Any]]:
        """Detect beliefs with high confidence but low evidence count."""
        warnings: list[dict[str, Any]] = []
        for belief in self._beliefs():
            confidence = float(belief.get("confidence", 0.0) or 0.0)
            evidence_count = int(belief.get("evidence_count", 0) or 0)
            if confidence >= self.OVERCONFIDENCE_THRESHOLD and evidence_count < self.MIN_BELIEF_EVIDENCE:
                warnings.append(
                    {
                        "type": "overconfidence",
                        "belief": belief.get("content") or belief.get("belief") or "unknown",
                        "message": "High confidence with low evidence",
                    }
                )
        return warnings

    def detect_context_confusion(self) -> list[dict[str, Any]]:
        """Identify edges that look context-specific but are treated as universal."""
        warnings: list[dict[str, Any]] = []
        for edge in self._causal_edges():
            contexts = edge.get("contexts")
            if isinstance(contexts, str):
                contexts = [contexts]
            if not isinstance(contexts, list):
                contexts = []

            universal = bool(edge.get("is_universal") or edge.get("applies_globally"))
            low_context_coverage = len([ctx for ctx in contexts if isinstance(ctx, str) and ctx.strip()]) <= 1
            if universal and low_context_coverage:
                warnings.append(
                    {
                        "type": "context_confusion",
                        "edge": f"{edge.get('cause', 'unknown')} → {edge.get('effect', 'unknown')}",
                        "message": "Rule may be context-specific but is treated as universal",
                    }
                )
        return warnings

    def generate_warnings(self) -> list[dict[str, Any]]:
        """Return a combined list of reasoning warnings for the agent."""
        return [
            *self.detect_false_causation(),
            *self.detect_overconfidence(),
            *self.detect_context_confusion(),
        ]

    def adjust_confidence(self) -> dict[str, Any]:
        """Lower confidence for suspicious beliefs/edges and return adjusted state."""
        state = deepcopy(self._state())
        beliefs = state.get("beliefs") if isinstance(state.get("beliefs"), list) else []
        edges = state.get("causal_edges") if isinstance(state.get("causal_edges"), list) else []

        for belief in beliefs:
            if not isinstance(belief, dict):
                continue
            confidence = float(belief.get("confidence", 0.0) or 0.0)
            evidence_count = int(belief.get("evidence_count", 0) or 0)
            if confidence >= self.OVERCONFIDENCE_THRESHOLD and evidence_count < self.MIN_BELIEF_EVIDENCE:
                belief["confidence"] = round(max(0.0, confidence - 0.15), 4)

        for edge in edges:
            if not isinstance(edge, dict):
                continue
            confidence = float(edge.get("confidence", 0.0) or 0.0)
            evidence_count = int(edge.get("evidence_count", 0) or 0)
            if confidence >= 0.5 and evidence_count < self.MIN_CAUSAL_EVIDENCE:
                edge["confidence"] = round(max(0.0, confidence - 0.1), 4)
                edge["uncertain"] = True

        return state
