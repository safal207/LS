"""Integrated decision pipeline for event -> counterfactuals -> strategy selection."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Set

from .counterfactual_engine import CounterfactualEngine
from .health_scheduler import ToolHealthcheckScheduler
from .observability import DecisionObservability
from .reflection_engine import ReflectionEngine
from .simulation_engine import StrategySimulationEngine
from .strategy_evolution_engine import StrategyEvolutionEngine
from .tool_runtime import ToolAdapter, ToolCallable, ToolRuntime


class DecisionPipeline:
    """Orchestrates counterfactual generation, strategy evolution, and action logging."""

    def __init__(
        self,
        cognitive_state: Dict[str, Any],
        low_confidence_threshold: float = 0.25,
        fallback_action: str = "retrieve_context",
        tool_registry: Dict[str, ToolCallable] | None = None,
        tool_adapters: Mapping[str, ToolAdapter] | None = None,
        sandbox_mode: bool = True,
        allowed_tool_actions: Set[str] | None = None,
        tool_failure_fallback_action: str = "structured_reasoning",
        tool_payload_builders: Mapping[str, Callable[[List[Dict[str, Any]]], Dict[str, Any]]] | None = None,
    ):
        self.cognitive_state = cognitive_state
        self.counterfactual_engine = CounterfactualEngine(cognitive_state)
        self.strategy_engine = StrategyEvolutionEngine(cognitive_state)
        self.simulation_engine = StrategySimulationEngine(cognitive_state)
        self.observability = DecisionObservability(cognitive_state)
        self.reflection_engine = ReflectionEngine(self.cognitive_state, window=50)
        self.low_confidence_threshold = low_confidence_threshold
        self.fallback_action = fallback_action
        self.tool_failure_fallback_action = tool_failure_fallback_action
        self.allowed_tool_actions = set(allowed_tool_actions) if allowed_tool_actions is not None else {"answer_with_tool", "retrieve_context"}
        self.tool_payload_builders = dict(tool_payload_builders or {})
        self.tool_runtime = ToolRuntime(
            cognitive_state,
            tool_registry=tool_registry,
            tool_adapters=tool_adapters,
            sandbox_mode=sandbox_mode,
        )

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
        final_action, fallback_reason = self._resolve_tool_failure_fallback(selected["recommended_action"], tool_execution)

        decision_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_count": len(event_sequence),
            "recommended_action": final_action,
            "predicted_outcome": selected["predicted_outcome"],
            "confidence": selected["confidence"],
            "calibrated_confidence": selected.get("calibrated_confidence", selected["confidence"]),
            "actual_outcome": actual_outcome,
            "success": success,
            "outcome_value": outcome_value,
            "ranked_strategies": ranked,
            "tool_execution": tool_execution,
            "fallback_reason": fallback_reason,
        }

        self._log_decision(decision_record)
        self._append_action_history(decision_record)
        self._update_metrics(decision_record)
        self._update_long_term_metrics()
        self.strategy_engine.update_from_result(
            action=final_action,
            predicted_outcome=selected["predicted_outcome"],
            actual_outcome=actual_outcome,
            success=success,
            outcome_value=outcome_value,
        )
        self.strategy_engine.update_causal_edges_from_feedback(
            action=final_action,
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

    def run_tool_healthchecks(self) -> Dict[str, Dict[str, Any]]:
        """Run active tool healthchecks and persist latest report."""
        return self.tool_runtime.run_active_healthchecks()

    def reflect_and_propose(self) -> List[Dict[str, Any]]:
        """Generate reflection proposals from current cognitive state."""
        return self.reflection_engine.generate_proposals(max_proposals=3)

    def get_session_replay(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Expose replay records for operator inspection."""
        return self.observability.get_session_replay(limit=limit)

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
                "tool_failure_fallback_action": self.tool_failure_fallback_action,
                "allowed_tool_actions": sorted(self.allowed_tool_actions),
            },
            "trends": self.observability.get_trend_summary(window=20),
            "last_decision_metrics": self.cognitive_state.get("last_decision_metrics", {}),
            "last_simulation_metrics": self.cognitive_state.get("last_simulation_metrics", {}),
            "tool_health": self.cognitive_state.get("tool_health", {}),
            "last_tool_healthcheck": self.cognitive_state.get("last_tool_healthcheck", {}),
        }

    def update_controls(
        self,
        low_confidence_threshold: float | None = None,
        fallback_action: str | None = None,
        tool_failure_fallback_action: str | None = None,
    ) -> None:
        """Update runtime decision controls without redeploy."""
        if low_confidence_threshold is not None:
            self.low_confidence_threshold = max(0.0, min(1.0, low_confidence_threshold))
        if fallback_action is not None:
            self.fallback_action = fallback_action
        if tool_failure_fallback_action is not None:
            self.tool_failure_fallback_action = tool_failure_fallback_action

    def register_action_activity(self, activity_type: str, details: Dict[str, Any] | None = None) -> None:
        """Append typed activity event for dashboard operational timeline."""
        activity_log = self.cognitive_state.setdefault("pipeline_activity", [])
        activity_log.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": activity_type,
                "details": details or {},
            }
        )


    def save_state(self, file_path: str) -> None:
        """Persist cognitive state snapshot to a JSON file."""
        with open(file_path, "w", encoding="utf-8") as handle:
            json.dump(self.cognitive_state, handle, ensure_ascii=False, indent=2)

    def load_state(self, file_path: str) -> None:
        """Load cognitive state snapshot from JSON and refresh bound engines."""
        with open(file_path, "r", encoding="utf-8") as handle:
            loaded_state = json.load(handle)

        self.cognitive_state.clear()
        self.cognitive_state.update(loaded_state)

    def evaluate_strategy_candidate(
        self,
        candidate_metrics: Dict[str, float],
        baseline_metrics: Dict[str, float],
        manual_override_reason: str | None = None,
    ) -> Dict[str, Any]:
        """Evaluate candidate against baseline using enforced strategy gate policy."""
        return self.strategy_engine.evaluate_strategy_candidate(
            candidate_metrics=candidate_metrics,
            baseline_metrics=baseline_metrics,
            manual_override_reason=manual_override_reason,
        )

    def promote_strategy_candidate(
        self,
        candidate_strategy: Dict[str, Any],
        candidate_metrics: Dict[str, float],
        baseline_metrics: Dict[str, float],
        manual_override_reason: str | None = None,
    ) -> Dict[str, Any]:
        """Mandatory lifecycle gate: evaluate and conditionally promote strategy candidate."""
        return self.strategy_engine.promote_strategy_candidate(
            candidate_strategy=candidate_strategy,
            candidate_metrics=candidate_metrics,
            baseline_metrics=baseline_metrics,
            manual_override_reason=manual_override_reason,
        )


    def save_state(self, path: str = "reflection_state.json") -> None:
        """Persist cognitive state to JSON for operator workflows."""
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(self.cognitive_state, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load_state(cls, path: str = "reflection_state.json") -> "DecisionPipeline":
        """Load pipeline cognitive state from JSON or initialize empty state."""
        state_path = Path(path)
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
        else:
            state = {}
        return cls(state)

    def _maybe_execute_tool(self, action: str | None, event_sequence: List[Dict[str, Any]]) -> Dict[str, Any] | None:
        """Execute tool-backed actions with runtime guardrails."""
        if action not in self.allowed_tool_actions:
            return None

        payload = self._build_tool_payload(action, event_sequence)
        execution = self.tool_runtime.execute(action, payload)
        if execution.get("status") in {"error", "blocked", "timeout"}:
            execution["fallback_action"] = self.tool_failure_fallback_action
        return execution

    def _build_tool_payload(self, action: str, event_sequence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build action-aware payloads for adapter-backed tool execution."""
        builder = self.tool_payload_builders.get(action)
        if builder is not None:
            return builder(event_sequence)

        payload: Dict[str, Any] = {"event_sequence": event_sequence}
        if action == "retrieve_context":
            payload["query"] = event_sequence[-1].get("value") if event_sequence else None
        return payload

    def _resolve_tool_failure_fallback(
        self,
        selected_action: str,
        tool_execution: Dict[str, Any] | None,
    ) -> tuple[str, str | None]:
        """Switch to fallback action on tool runtime failure outcomes."""
        if not tool_execution:
            return selected_action, None

        status = tool_execution.get("status")
        if status in {"error", "blocked", "timeout"}:
            reason = tool_execution.get("reason")
            if not reason:
                reason_map = {"error": "tool_error", "timeout": "tool_timeout", "blocked": "tool_blocked"}
                reason = reason_map.get(status, status)
            return self.tool_failure_fallback_action, reason

        return selected_action, None

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
                "fallback_reason": decision_record.get("fallback_reason"),
            }
        )

    def _update_metrics(self, decision_record: Dict[str, Any]) -> None:
        """Store baseline decision metrics in cognitive state."""
        self.cognitive_state["last_decision_metrics"] = {
            "confidence": decision_record["confidence"],
            "calibrated_confidence": decision_record["calibrated_confidence"],
            "predicted_outcome": decision_record["predicted_outcome"],
            "action_success": decision_record["success"],
            "fallback_reason": decision_record.get("fallback_reason"),
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
