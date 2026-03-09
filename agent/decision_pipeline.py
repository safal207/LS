"""Integrated decision pipeline for event -> counterfactuals -> strategy selection."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from .counterfactual_engine import CounterfactualEngine
from .simulation_engine import StrategySimulationEngine
from .strategy_evolution_engine import StrategyEvolutionEngine
from .tool_runtime import ToolCallable, ToolRuntime


class DecisionPipeline:
    """Orchestrates counterfactual generation, strategy evolution, and action logging."""

    def __init__(
        self,
        cognitive_state: Dict[str, Any],
        low_confidence_threshold: float = 0.25,
        fallback_action: str = "retrieve_context",
        tool_registry: Dict[str, ToolCallable] | None = None,
        sandbox_mode: bool = True,
    ):
        self.cognitive_state = cognitive_state
        self.counterfactual_engine = CounterfactualEngine(cognitive_state)
        self.strategy_engine = StrategyEvolutionEngine(cognitive_state)
        self.simulation_engine = StrategySimulationEngine(cognitive_state)
        self.low_confidence_threshold = low_confidence_threshold
        self.fallback_action = fallback_action
        self.tool_runtime = ToolRuntime(cognitive_state, tool_registry=tool_registry, sandbox_mode=sandbox_mode)

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

        tool_execution = self._maybe_execute_tool(selected["recommended_action"], event_sequence)

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
            "tool_execution": tool_execution,
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
        self.strategy_engine.update_causal_edges_from_feedback(
            action=selected["recommended_action"],
            actual_outcome=actual_outcome,
            success=success,
        )
        return decision_record

    def run_simulation_cycle(self, scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run KPI simulation and feed results back into strategy evolution."""
        report = self.simulation_engine.run(scenarios)
        self.strategy_engine.ingest_simulation_feedback(report)
        self.cognitive_state["last_simulation_metrics"] = {
            "success_rate": report["success_rate"],
            "prediction_accuracy": report["prediction_accuracy"],
            "total_value": report["total_value"],
        }
        return report

    def get_visualization_snapshot(self) -> Dict[str, Any]:
        """Build operator-facing flow/heatmap snapshot from current state."""
        strategy_stats = self.cognitive_state.get("strategy_stats", {})
        heatmap = [
            {
                "action": action,
                "success_rate": (item.get("successes", 0) / item.get("attempts", 1)),
                "efficiency": (item.get("total_value", 0.0) / item.get("attempts", 1)),
            }
            for action, item in strategy_stats.items()
            if isinstance(item, dict) and item.get("attempts", 0) > 0
        ]

        return {
            "flow": "event -> counterfactuals -> strategy_evolution -> action_selection",
            "heatmap": sorted(heatmap, key=lambda x: x["success_rate"], reverse=True),
            "controls": {
                "low_confidence_threshold": self.low_confidence_threshold,
                "fallback_action": self.fallback_action,
            },
            "last_decision_metrics": self.cognitive_state.get("last_decision_metrics", {}),
            "last_simulation_metrics": self.cognitive_state.get("last_simulation_metrics", {}),
        }

    def update_controls(self, low_confidence_threshold: float | None = None, fallback_action: str | None = None) -> None:
        """Update runtime decision controls without redeploy."""
        if low_confidence_threshold is not None:
            self.low_confidence_threshold = max(0.0, min(1.0, low_confidence_threshold))
        if fallback_action is not None:
            self.fallback_action = fallback_action

    def _maybe_execute_tool(self, action: str | None, event_sequence: List[Dict[str, Any]]) -> Dict[str, Any] | None:
        """Execute tool-backed actions with runtime guardrails."""
        if action not in {"answer_with_tool", "retrieve_context"}:
            return None

        payload = {"event_sequence": event_sequence}
        return self.tool_runtime.execute(action, payload)

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
