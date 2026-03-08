"""Counterfactual reasoning engine for cognitive agents."""

from __future__ import annotations

from typing import Any, Dict, List


class CounterfactualEngine:
    """Simulate alternative decisions and estimate outcomes using causal graph."""

    def __init__(self, cognitive_state: Dict[str, Any]):
        self.cognitive_state = cognitive_state

    def generate_counterfactuals(self, event_sequence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate alternative action scenarios for a given sequence."""
        last_action = None
        for event in reversed(event_sequence):
            if event.get("type") in ("action", "decision"):
                last_action = event.get("value")
                break

        alternatives = self._generate_alternatives(last_action)

        counterfactuals = []
        for action in alternatives:
            outcome = self.simulate_outcome(action)
            counterfactuals.append(
                {
                    "alternative_action": action,
                    "predicted_outcome": outcome.get("predicted_outcome"),
                    "confidence": outcome.get("confidence"),
                }
            )

        return counterfactuals

    def simulate_outcome(self, action: str) -> Dict[str, Any]:
        """Predict likely outcomes using the causal edges."""
        causal_edges = self._get_causal_edges()
        matched_edges = [e for e in causal_edges if e.get("cause") == action]
        if not matched_edges:
            return {"predicted_outcome": "unknown", "confidence": 0.0}

        best_edge = max(matched_edges, key=lambda e: e.get("confidence", 0))
        return {
            "predicted_outcome": best_edge.get("effect", "unknown"),
            "confidence": best_edge.get("confidence", 0.0),
        }

    def evaluate_alternatives(self, alternatives: List[str]) -> List[Dict[str, Any]]:
        """Score each alternative based on predicted outcomes."""
        scored = []
        for action in alternatives:
            outcome = self.simulate_outcome(action)
            scored.append(
                {
                    "action": action,
                    "predicted_outcome": outcome.get("predicted_outcome"),
                    "confidence": outcome.get("confidence"),
                }
            )
        return sorted(scored, key=lambda x: x["confidence"], reverse=True)

    def suggest_better_action(self, event_sequence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Return best alternative action based on causal graph."""
        counterfactuals = self.generate_counterfactuals(event_sequence)
        if not counterfactuals:
            return {"recommended_action": None, "expected_outcome": None, "confidence": 0.0}
        best = max(counterfactuals, key=lambda x: x.get("confidence", 0.0))
        return {
            "recommended_action": best["alternative_action"],
            "expected_outcome": best["predicted_outcome"],
            "confidence": best["confidence"],
        }

    def _generate_alternatives(self, last_action: str | None) -> List[str]:
        """Simple alternative generation rules."""
        base_actions = {
            "answer_directly",
            "answer_with_tool",
            "structured_reasoning",
            "retrieve_context",
        }
        if last_action:
            base_actions.discard(last_action)
        return list(base_actions)

    def _get_causal_edges(self) -> List[Dict[str, Any]]:
        """Retrieve causal edges from cognitive state."""
        edges = self.cognitive_state.get("causal_edges")
        if isinstance(edges, list):
            return edges

        graph = self.cognitive_state.get("causal_graph", {})
        if isinstance(graph, dict) and isinstance(graph.get("edges"), list):
            return graph["edges"]
        return []
