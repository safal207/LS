from __future__ import annotations

from typing import Any


class CounterfactualEngine:
    """Deterministic counterfactual simulator based on learned causal edges."""

    _DEFAULT_ALTERNATIVES: tuple[str, ...] = ("tool_use", "structured_reasoning", "retrieve_context")
    _ACTION_REWRITES: dict[str, tuple[str, ...]] = {
        "no_tool": ("tool_use", "retrieve_context", "structured_reasoning"),
        "answer_directly": ("structured_reasoning", "tool_use", "retrieve_context"),
        "answer_with_tool": ("tool_use",),
    }

    def __init__(self, cognitive_state: dict[str, Any] | None):
        self.cognitive_state = cognitive_state or {}

    def _causal_edges(self) -> list[dict[str, Any]]:
        state = self.cognitive_state.get("state", self.cognitive_state)
        raw_edges = state.get("causal_edges") if isinstance(state, dict) else []
        if not isinstance(raw_edges, list):
            return []
        return [edge for edge in raw_edges if isinstance(edge, dict)]

    def _extract_actions(self, event_sequence: list[dict[str, Any]]) -> list[str]:
        actions: list[str] = []
        for event in event_sequence:
            if not isinstance(event, dict):
                continue
            event_type = event.get("type")
            value = event.get("value")
            if event_type in {"decision", "action"} and isinstance(value, str) and value.strip():
                actions.append(value.strip())
        return actions

    def _known_causes(self) -> list[str]:
        causes = {
            str(edge.get("cause")).strip()
            for edge in self._causal_edges()
            if isinstance(edge.get("cause"), str) and str(edge.get("cause")).strip()
        }
        return sorted(causes)

    def generate_counterfactuals(self, event_sequence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Generate alternative action scenarios for a given sequence."""
        observed_actions = self._extract_actions(event_sequence)
        alternatives = self._build_alternatives(observed_actions)
        return self.evaluate_alternatives(alternatives)

    def _build_alternatives(self, observed_actions: list[str]) -> list[str]:
        alternatives: list[str] = []
        for action in observed_actions:
            alternatives.extend(self._ACTION_REWRITES.get(action, ()))

        alternatives.extend(self._known_causes())
        if not alternatives:
            alternatives.extend(self._DEFAULT_ALTERNATIVES)

        observed_set = set(observed_actions)
        deduped: list[str] = []
        for action in alternatives:
            if action in observed_set or action in deduped:
                continue
            deduped.append(action)
        return deduped

    def simulate_outcome(self, action: str) -> dict[str, Any]:
        """Predict likely outcomes using the causal graph."""
        best_edge: dict[str, Any] | None = None
        best_confidence = float("-inf")

        for edge in self._causal_edges():
            if edge.get("cause") != action:
                continue
            confidence = float(edge.get("confidence", 0.0) or 0.0)
            if confidence > best_confidence:
                best_confidence = confidence
                best_edge = edge

        if best_edge is None:
            return {"predicted_outcome": "unknown", "confidence": 0.0}

        return {
            "predicted_outcome": best_edge.get("effect", "unknown"),
            "confidence": round(float(best_edge.get("confidence", 0.0) or 0.0), 4),
        }

    def evaluate_alternatives(self, alternatives: list[str]) -> list[dict[str, Any]]:
        """Score each alternative based on predicted outcomes."""
        scored: list[dict[str, Any]] = []
        for action in alternatives:
            prediction = self.simulate_outcome(action)
            scored.append(
                {
                    "alternative_action": action,
                    "predicted_outcome": prediction["predicted_outcome"],
                    "confidence": prediction["confidence"],
                }
            )

        return sorted(scored, key=lambda item: (-float(item["confidence"]), str(item["alternative_action"])))

    def suggest_better_action(self, event_sequence: list[dict[str, Any]]) -> dict[str, Any]:
        """Return the highest-scoring deterministic counterfactual action."""
        scenarios = self.generate_counterfactuals(event_sequence)
        if not scenarios:
            return {
                "recommended_action": None,
                "expected_outcome": "unknown",
                "confidence": 0.0,
            }

        best = scenarios[0]
        return {
            "recommended_action": best["alternative_action"],
            "expected_outcome": best["predicted_outcome"],
            "confidence": best["confidence"],
        }
