"""Strategy evolution module for post-counterfactual action ranking and learning."""

from __future__ import annotations

from typing import Any, Dict, List


class StrategyEvolutionEngine:
    """Rank strategy candidates and update their long-term performance."""

    def __init__(self, cognitive_state: Dict[str, Any]):
        self.cognitive_state = cognitive_state

    def rank_strategies(self, counterfactuals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rank counterfactual strategies with historical performance adjustment."""
        ranked: List[Dict[str, Any]] = []
        for item in counterfactuals:
            action = item.get("alternative_action")
            confidence = float(item.get("confidence", 0.0) or 0.0)
            success_rate = self._get_success_rate(action)
            weighted_score = 0.7 * confidence + 0.3 * success_rate

            ranked.append(
                {
                    "action": action,
                    "predicted_outcome": item.get("predicted_outcome"),
                    "confidence": confidence,
                    "historical_success_rate": success_rate,
                    "weighted_score": weighted_score,
                }
            )

        return sorted(ranked, key=lambda x: x["weighted_score"], reverse=True)

    def choose_action(self, ranked_strategies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Choose top ranked strategy."""
        if not ranked_strategies:
            return {
                "recommended_action": None,
                "predicted_outcome": None,
                "confidence": 0.0,
                "weighted_score": 0.0,
            }

        top = ranked_strategies[0]
        return {
            "recommended_action": top["action"],
            "predicted_outcome": top.get("predicted_outcome"),
            "confidence": top.get("confidence", 0.0),
            "weighted_score": top.get("weighted_score", 0.0),
        }

    def update_from_result(
        self,
        action: str | None,
        predicted_outcome: str | None,
        actual_outcome: str | None,
        success: bool | None,
    ) -> None:
        """Update strategy historical stats using observed outcomes."""
        if not action:
            return

        strategy_stats = self.cognitive_state.setdefault("strategy_stats", {})
        current = strategy_stats.setdefault(action, {"attempts": 0, "successes": 0})
        current["attempts"] += 1

        inferred_success = success
        if inferred_success is None and predicted_outcome is not None and actual_outcome is not None:
            inferred_success = predicted_outcome == actual_outcome

        if inferred_success:
            current["successes"] += 1

    def _get_success_rate(self, action: str | None) -> float:
        """Return historical success rate for action, defaulting to neutral prior."""
        if not action:
            return 0.5

        strategy_stats = self.cognitive_state.get("strategy_stats", {})
        item = strategy_stats.get(action)
        if not isinstance(item, dict):
            return 0.5

        attempts = int(item.get("attempts", 0) or 0)
        successes = int(item.get("successes", 0) or 0)
        if attempts <= 0:
            return 0.5

        return max(0.0, min(1.0, successes / attempts))
