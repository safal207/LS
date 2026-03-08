"""Strategy evolution engine for policy discovery and reuse."""

from __future__ import annotations

from typing import Any

from .cognitive_illusions import CognitiveIllusionDetector


class StrategyEvolutionEngine:
    """Discovers robust strategies and persists them as reusable policies."""

    def __init__(self, cognitive_state: dict[str, Any]):
        self.cognitive_state = cognitive_state

    def discover_best_strategies(self, counterfactual_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Select high-value alternative actions and filter risky strategies."""
        if not isinstance(counterfactual_results, list):
            return []

        warnings = self._generate_strategy_warnings(counterfactual_results)
        risky_actions = {
            warning.get("belief")
            for warning in warnings
            if warning.get("type") == "overconfidence" and isinstance(warning.get("belief"), str)
        }

        candidates: list[dict[str, Any]] = []
        for strategy in counterfactual_results:
            if not isinstance(strategy, dict):
                continue
            action = self._strategy_key(strategy)
            if action in risky_actions:
                continue
            candidates.append(
                {
                    "action": action,
                    "situation": strategy.get("situation", {}),
                    "predicted_outcome": float(strategy.get("predicted_outcome", 0.0)),
                    "confidence": float(strategy.get("confidence", 0.0)),
                    "evidence_count": int(strategy.get("evidence_count", 0)),
                }
            )

        return sorted(
            candidates,
            key=lambda item: (item["predicted_outcome"], item["confidence"]),
            reverse=True,
        )

    def store_as_policies(self, strategies: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Persist selected strategies as policies in the shared cognitive state."""
        policies = self.cognitive_state.setdefault("policies", [])
        if not isinstance(policies, list):
            policies = []
            self.cognitive_state["policies"] = policies

        indexed = {
            self._policy_identity(policy): policy
            for policy in policies
            if isinstance(policy, dict)
        }

        for strategy in strategies:
            if not isinstance(strategy, dict):
                continue
            policy = {
                "action": self._strategy_key(strategy),
                "situation": strategy.get("situation", {}),
                "predicted_outcome": float(strategy.get("predicted_outcome", 0.0)),
                "confidence": float(strategy.get("confidence", 0.0)),
            }
            indexed[self._policy_identity(policy)] = policy

        self.cognitive_state["policies"] = list(indexed.values())
        return self.cognitive_state["policies"]

    def suggest_policy(self, situation: dict[str, Any]) -> dict[str, Any]:
        """Return the most promising stored policy for the current situation."""
        policies = self.cognitive_state.get("policies", [])
        if not isinstance(policies, list) or not policies:
            return {}

        best_policy: dict[str, Any] | None = None
        best_score = (-1.0, -1.0, -1.0, -1.0)

        for policy in policies:
            if not isinstance(policy, dict):
                continue
            ratio, matched_keys = self._situation_match_score(situation, policy.get("situation", {}))
            score = (
                ratio,
                float(matched_keys),
                float(policy.get("predicted_outcome", 0.0)),
                float(policy.get("confidence", 0.0)),
            )
            if score > best_score:
                best_score = score
                best_policy = policy

        return best_policy or {}

    def _generate_strategy_warnings(self, strategies: list[dict[str, Any]]) -> list[dict[str, str]]:
        beliefs: list[dict[str, Any]] = []
        for strategy in strategies:
            if not isinstance(strategy, dict):
                continue
            beliefs.append(
                {
                    "content": self._strategy_key(strategy),
                    "confidence": float(strategy.get("confidence", 0.0)),
                    "evidence_count": int(strategy.get("evidence_count", 0)),
                }
            )

        detector_state = dict(self.cognitive_state)
        detector_state["beliefs"] = beliefs
        detector = CognitiveIllusionDetector(detector_state)
        return detector.generate_warnings()

    def _strategy_key(self, strategy: dict[str, Any]) -> str:
        return str(strategy.get("action", "unknown_action"))

    def _policy_identity(self, policy: dict[str, Any]) -> tuple[str, str]:
        action = str(policy.get("action", "unknown_action"))
        situation = policy.get("situation", {})
        if not isinstance(situation, dict):
            return action, ""
        frozen_situation = "|".join(f"{key}={situation[key]}" for key in sorted(situation))
        return action, frozen_situation

    def _situation_match_score(self, current: dict[str, Any], reference: dict[str, Any]) -> tuple[float, int]:
        if not isinstance(current, dict) or not isinstance(reference, dict) or not reference:
            return 0.0, 0

        matches = 0
        for key, value in reference.items():
            if key in current and current[key] == value:
                matches += 1
        return matches / len(reference), matches
