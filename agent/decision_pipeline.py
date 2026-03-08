"""Integrated decision pipeline for event -> counterfactuals -> strategy selection."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from .counterfactual_engine import CounterfactualEngine
from .strategy_evolution_engine import StrategyEvolutionEngine


class DecisionPipeline:
    """Orchestrates counterfactual generation, strategy evolution, and action logging."""

    def __init__(
        self,
        cognitive_state: Dict[str, Any],
        low_confidence_threshold: float = 0.25,
        fallback_action: str = "retrieve_context",
    ):
        self.cognitive_state = cognitive_state
        self.counterfactual_engine = CounterfactualEngine(cognitive_state)
        self.strategy_engine = StrategyEvolutionEngine(cognitive_state)
        self.low_confidence_threshold = low_confidence_threshold
        self.fallback_action = fallback_action

    def run(
        self,
        event_sequence: List[Dict[str, Any]],
        actual_outcome: str | None = None,
        success: bool | None = None,
        outcome_value: float | None = None,
    ) -> Dict[str, Any]:
        """Execute full decision pipeline and persist metrics/logs in cognitive state."""
        counterfactuals = self.counterfactual_engine.generate_counterfactuals(event_sequence)
        ranked = self.strategy_engine.rank_strategies(counterfactuals)
        selected = self.strategy_engine.choose_action(ranked)

        confidence = selected.get("calibrated_confidence", selected.get("confidence", 0.0))
        if selected["recommended_action"] is None or confidence < self.low_confidence_threshold:
            selected = {
                "recommended_action": self.fallback_action,
                "predicted_outcome": "unknown",
                "confidence": selected.get("confidence", 0.0),
                "calibrated_confidence": confidence,
                "weighted_score": selected.get("weighted_score", 0.0),
            }

        decision_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_count": len(event_sequence),
            "recommended_action": selected["recommended_action"],
            "predicted_outcome": selected["predicted_outcome"],
            "confidence": selected["confidence"],
            "calibrated_confidence": selected.get("calibrated_confidence", selected["confidence"]),
            "actual_outcome": actual_outcome,
            "success": success,
            "outcome_value": outcome_value,
            "ranked_strategies": ranked,
        }

        self._log_decision(decision_record)
        self._append_action_history(decision_record)
        self._update_metrics(decision_record)
        self._update_long_term_metrics()
        self.strategy_engine.update_from_result(
            action=selected["recommended_action"],
            predicted_outcome=selected["predicted_outcome"],
            actual_outcome=actual_outcome,
            success=success,
            outcome_value=outcome_value,
        )
        return decision_record

    def _log_decision(self, decision_record: Dict[str, Any]) -> None:
        """Append decision record to cognitive state action log."""
        action_log = self.cognitive_state.setdefault("action_log", [])
        action_log.append(decision_record)

    def _append_action_history(self, decision_record: Dict[str, Any]) -> None:
        """Append compact history records for long-term learning."""
        action_history = self.cognitive_state.setdefault("action_history", [])
        action_history.append(
            {
                "timestamp": decision_record["timestamp"],
                "action": decision_record["recommended_action"],
                "predicted_outcome": decision_record["predicted_outcome"],
                "actual_outcome": decision_record["actual_outcome"],
                "success": decision_record["success"],
                "outcome_value": decision_record["outcome_value"],
            }
        )

    def _update_metrics(self, decision_record: Dict[str, Any]) -> None:
        """Store baseline decision metrics in cognitive state."""
        self.cognitive_state["last_decision_metrics"] = {
            "confidence": decision_record["confidence"],
            "calibrated_confidence": decision_record["calibrated_confidence"],
            "predicted_outcome": decision_record["predicted_outcome"],
            "action_success": decision_record["success"],
        }

    def _update_long_term_metrics(self) -> None:
        """Update simple long-term learning metrics from action history."""
        history = self.cognitive_state.get("action_history", [])
        if not history:
            return

        successes = sum(1 for item in history if item.get("success") is True)
        attempts = len(history)
        value_sum = sum(float(item.get("outcome_value", 0.0) or 0.0) for item in history)

        self.cognitive_state["long_term_metrics"] = {
            "total_attempts": attempts,
            "success_rate": successes / attempts,
            "total_value": value_sum,
            "average_value": value_sum / attempts,
        }
