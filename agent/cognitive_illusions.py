"""Cognitive illusion detection for belief and causal state."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


class CognitiveIllusionDetector:
    """Detects reasoning illusions in beliefs and causal edges."""

    def __init__(self, cognitive_state: dict[str, Any]):
        self.cognitive_state = cognitive_state
        self.overconfidence_threshold = 0.8
        self.false_causation_threshold = 0.75
        self.min_evidence_count = 5

    def detect_false_causation(self) -> list[dict[str, str]]:
        """Identify causal edges with high confidence but poor evidence support."""
        warnings: list[dict[str, str]] = []
        for edge in self._get_causal_edges():
            confidence = float(edge.get("confidence", 0.0))
            evidence_count = int(edge.get("evidence_count", 0))
            if confidence >= self.false_causation_threshold and evidence_count < self.min_evidence_count:
                cause = edge.get("cause", "unknown_cause")
                effect = edge.get("effect", "unknown_effect")
                warnings.append(
                    {
                        "type": "false_causation",
                        "edge": f"{cause} → {effect}",
                        "message": "Possible correlation without sufficient support",
                    }
                )
        return warnings

    def detect_overconfidence(self) -> list[dict[str, str]]:
        """Detect beliefs with high confidence but low evidence count."""
        warnings: list[dict[str, str]] = []
        for belief in self._get_beliefs():
            confidence = float(belief.get("confidence", 0.0))
            evidence_count = int(belief.get("evidence_count", 0))
            if confidence >= self.overconfidence_threshold and evidence_count < self.min_evidence_count:
                warnings.append(
                    {
                        "type": "overconfidence",
                        "belief": str(belief.get("content", "<unknown belief>")),
                        "message": "High confidence with low evidence",
                    }
                )
        return warnings

    def detect_context_confusion(self) -> list[dict[str, str]]:
        """Find context-specific causal rules misread as universal ones."""
        warnings: list[dict[str, str]] = []
        for edge in self._get_causal_edges():
            context_specific = bool(edge.get("context_specific", False))
            treated_as_universal = bool(edge.get("treated_as_universal", False))
            if context_specific and treated_as_universal:
                cause = edge.get("cause", "unknown_cause")
                effect = edge.get("effect", "unknown_effect")
                context = edge.get("context")
                message = "Context-bound relationship used as universal rule"
                if context:
                    message = f"Context-bound relationship from '{context}' used as universal rule"
                warnings.append(
                    {
                        "type": "context_confusion",
                        "edge": f"{cause} → {effect}",
                        "message": message,
                    }
                )
        return warnings

    def generate_warnings(self) -> list[dict[str, str]]:
        """Return a combined list of all currently detected cognitive warnings."""
        return [
            *self.detect_overconfidence(),
            *self.detect_false_causation(),
            *self.detect_context_confusion(),
        ]

    def adjust_confidence(self) -> dict[str, Any]:
        """Lower confidence for suspicious beliefs/edges and mark edges uncertain."""
        adjusted_state = deepcopy(self.cognitive_state)

        for belief in adjusted_state.get("beliefs", []):
            confidence = float(belief.get("confidence", 0.0))
            evidence_count = int(belief.get("evidence_count", 0))
            if confidence >= self.overconfidence_threshold and evidence_count < self.min_evidence_count:
                belief["confidence"] = round(max(0.0, confidence - 0.2), 3)
                belief["uncertain"] = True

        for edge in self._get_causal_edges(state=adjusted_state):
            confidence = float(edge.get("confidence", 0.0))
            evidence_count = int(edge.get("evidence_count", 0))
            if confidence >= self.false_causation_threshold and evidence_count < self.min_evidence_count:
                edge["confidence"] = round(max(0.0, confidence - 0.2), 3)
                edge["uncertain"] = True
            if bool(edge.get("context_specific", False)) and bool(edge.get("treated_as_universal", False)):
                edge["uncertain"] = True

        self.cognitive_state = adjusted_state
        return adjusted_state

    def _get_beliefs(self) -> list[dict[str, Any]]:
        beliefs = self.cognitive_state.get("beliefs", [])
        return beliefs if isinstance(beliefs, list) else []

    def _get_causal_edges(self, state: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        current_state = state if state is not None else self.cognitive_state
        edges = current_state.get("causal_edges")
        if isinstance(edges, list):
            return edges

        graph = current_state.get("causal_graph", {})
        if isinstance(graph, dict) and isinstance(graph.get("edges"), list):
            return graph["edges"]

        return []
