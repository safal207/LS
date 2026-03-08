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
    ) -> Dict[str, Any]:
        """Execute full decision pipeline and persist metrics/logs in cognitive state."""
        counterfactuals = self.counterfactual_engine.generate_counterfactuals(event_sequence)
        ranked = self.strategy_engine.rank_strategies(counterfactuals)
        selected = self.strategy_engine.choose_action(ranked)

        if selected["recommended_action"] is None or selected["confidence"] < self.low_confidence_threshold:
            selected = {
                "recommended_action": self.fallback_action,
                "predicted_outcome": "unknown",
                "confidence": selected.get("confidence", 0.0),
                "weighted_score": selected.get("weighted_score", 0.0),
            }

        decision_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_count": len(event_sequence),
            "recommended_action": selected["recommended_action"],
            "predicted_outcome": selected["predicted_outcome"],
            "confidence": selected["confidence"],
            "actual_outcome": actual_outcome,
            "success": success,
            "ranked_strategies": ranked,
        }

        self._log_decision(decision_record)
        self._update_metrics(decision_record)
        self.strategy_engine.update_from_result(
            action=selected["recommended_action"],
            predicted_outcome=selected["predicted_outcome"],
            actual_outcome=actual_outcome,
            success=success,
        )
        return decision_record

    def _log_decision(self, decision_record: Dict[str, Any]) -> None:
        """Append decision record to cognitive state action log."""
        action_log = self.cognitive_state.setdefault("action_log", [])
        action_log.append(decision_record)

    def _update_metrics(self, decision_record: Dict[str, Any]) -> None:
        """Store baseline decision metrics in cognitive state."""
        self.cognitive_state["last_decision_metrics"] = {
            "confidence": decision_record["confidence"],
            "predicted_outcome": decision_record["predicted_outcome"],
            "action_success": decision_record["success"],
        }
