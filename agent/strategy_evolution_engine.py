"""Strategy evolution module for post-counterfactual action ranking and learning."""

from __future__ import annotations

from datetime import datetime, timezone
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
            efficiency = self._get_efficiency(action)
            calibrated_confidence = self._calibrate_confidence(action, confidence, success_rate)
            weighted_score = 0.6 * calibrated_confidence + 0.25 * success_rate + 0.15 * efficiency

            ranked.append(
                {
                    "action": action,
                    "predicted_outcome": item.get("predicted_outcome"),
                    "confidence": confidence,
                    "calibrated_confidence": calibrated_confidence,
                    "historical_success_rate": success_rate,
                    "historical_efficiency": efficiency,
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
                "calibrated_confidence": 0.0,
                "weighted_score": 0.0,
            }

        top = ranked_strategies[0]
        return {
            "recommended_action": top["action"],
            "predicted_outcome": top.get("predicted_outcome"),
            "confidence": top.get("confidence", 0.0),
            "calibrated_confidence": top.get("calibrated_confidence", 0.0),
            "weighted_score": top.get("weighted_score", 0.0),
        }

    def update_from_result(
        self,
        action: str | None,
        predicted_outcome: str | None,
        actual_outcome: str | None,
        success: bool | None,
        outcome_value: float | None = None,
    ) -> None:
        """Update strategy historical stats using observed outcomes."""
        if not action:
            return

        strategy_stats = self.cognitive_state.setdefault("strategy_stats", {})
        current = strategy_stats.setdefault(
            action,
            {
                "attempts": 0,
                "successes": 0,
                "total_value": 0.0,
                "overestimation_events": 0,
            },
        )
        current["attempts"] += 1

        inferred_success = success
        if inferred_success is None and predicted_outcome is not None and actual_outcome is not None:
            inferred_success = predicted_outcome == actual_outcome

        if inferred_success:
            current["successes"] += 1

        if outcome_value is not None:
            current["total_value"] += float(outcome_value)

    def update_causal_edges_from_feedback(
        self,
        action: str | None,
        actual_outcome: str | None,
        success: bool | None,
        learning_rate: float = 0.1,
    ) -> None:
        """Update or create causal edges from observed action outcomes."""
        if not action or actual_outcome is None:
            return

        edges = self.cognitive_state.setdefault("causal_edges", [])
        if not isinstance(edges, list):
            return

        match = None
        for edge in edges:
            if edge.get("cause") == action and edge.get("effect") == actual_outcome:
                match = edge
                break

        delta = learning_rate if success is not False else -learning_rate
        if match is None:
            base_confidence = 0.5 + (learning_rate if success else -learning_rate)
            edges.append(
                {
                    "cause": action,
                    "effect": actual_outcome,
                    "confidence": max(0.0, min(1.0, base_confidence)),
                }
            )
            return

        current_conf = float(match.get("confidence", 0.0) or 0.0)
        match["confidence"] = max(0.0, min(1.0, current_conf + delta))

    def ingest_simulation_feedback(self, simulation_report: Dict[str, Any]) -> None:
        """Use simulation runs to improve strategy statistics."""
        for result in simulation_report.get("results", []):
            self.update_from_result(
                action=result.get("action"),
                predicted_outcome=result.get("predicted_outcome"),
                actual_outcome=result.get("actual_outcome"),
                success=result.get("success"),
                outcome_value=result.get("outcome_value"),
            )
            self.update_causal_edges_from_feedback(
                action=result.get("action"),
                actual_outcome=result.get("actual_outcome"),
                success=result.get("success"),
                learning_rate=0.05,
            )

    def evaluate_strategy_candidate(
        self,
        candidate_metrics: Dict[str, float],
        baseline_metrics: Dict[str, float],
        manual_override_reason: str | None = None,
    ) -> Dict[str, Any]:
        """Evaluate candidate strategy against baseline promotion gate policy."""
        success_rate_delta = float(candidate_metrics.get("success_rate", 0.0) or 0.0) - float(
            baseline_metrics.get("success_rate", 0.0) or 0.0
        )
        prediction_accuracy_delta = float(candidate_metrics.get("prediction_accuracy", 0.0) or 0.0) - float(
            baseline_metrics.get("prediction_accuracy", 0.0) or 0.0
        )
        average_value_delta = float(candidate_metrics.get("average_value", 0.0) or 0.0) - float(
            baseline_metrics.get("average_value", 0.0) or 0.0
        )

        acceptance_policy = {
            "success_rate_delta_min": 0.0,
            "prediction_accuracy_delta_min": -0.01,
            "average_value_delta_min": 0.0,
        }

        epsilon = 1e-9
        checks = {
            "success_rate": success_rate_delta + epsilon >= acceptance_policy["success_rate_delta_min"],
            "prediction_accuracy": prediction_accuracy_delta + epsilon >= acceptance_policy["prediction_accuracy_delta_min"],
            "average_value": average_value_delta + epsilon >= acceptance_policy["average_value_delta_min"],
        }

        accepted_by_policy = all(checks.values())
        accepted = accepted_by_policy or bool(manual_override_reason)

        gate_result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "accepted": accepted,
            "accepted_by_policy": accepted_by_policy,
            "manual_override_reason": manual_override_reason,
            "deltas": {
                "success_rate_delta": success_rate_delta,
                "prediction_accuracy_delta": prediction_accuracy_delta,
                "average_value_delta": average_value_delta,
            },
            "checks": checks,
            "acceptance_policy": acceptance_policy,
            "candidate_metrics": candidate_metrics,
            "baseline_metrics": baseline_metrics,
        }

        self.cognitive_state["last_strategy_gate"] = gate_result
        history = self.cognitive_state.setdefault("strategy_gate_history", [])
        if isinstance(history, list):
            history.append(gate_result)

        return gate_result

    def _calibrate_confidence(self, action: str | None, confidence: float, success_rate: float) -> float:
        """Down-weight overestimated strategies using observed success history."""
        if not action:
            return confidence

        strategy_stats = self.cognitive_state.get("strategy_stats", {})
        item = strategy_stats.get(action)
        if not isinstance(item, dict):
            return confidence

        attempts = int(item.get("attempts", 0) or 0)
        if attempts < 3:
            return confidence

        overestimation = max(0.0, confidence - success_rate)
        if overestimation > 0.2:
            item["overestimation_events"] = int(item.get("overestimation_events", 0) or 0) + 1

        penalty = min(0.35, overestimation * 0.5)
        return max(0.0, confidence - penalty)

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

    def _get_efficiency(self, action: str | None) -> float:
        """Return normalized long-term value per attempt for the action."""
        if not action:
            return 0.5

        strategy_stats = self.cognitive_state.get("strategy_stats", {})
        item = strategy_stats.get(action)
        if not isinstance(item, dict):
            return 0.5

        attempts = int(item.get("attempts", 0) or 0)
        if attempts <= 0:
            return 0.5

        total_value = float(item.get("total_value", 0.0) or 0.0)
        per_attempt = total_value / attempts
        return max(0.0, min(1.0, per_attempt))
