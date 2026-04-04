"""Integrated decision pipeline for event -> counterfactuals -> strategy selection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Set

from .counterfactual_engine import CounterfactualEngine
from .cognition import (
    CognitiveEventMesh,
    CognitiveIdentity,
    CognitiveReducer,
    CognitiveStore,
    CognitiveTransaction,
    CognitiveTransactionLog,
    LTPEnvelope,
)
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
        self.cognitive_event_mesh = CognitiveEventMesh()
        self.cognitive_transaction_log = CognitiveTransactionLog(event_mesh=self.cognitive_event_mesh)
        self.cognitive_reducer = CognitiveReducer()
        self.cognitive_store = CognitiveStore(self.cognitive_transaction_log, self.cognitive_reducer, initial_state=self.cognitive_state)
        identity_payload = self.cognitive_state.get("cognitive_identity", {})
        self.cognitive_identity = (
            CognitiveIdentity.from_dict(identity_payload)
            if isinstance(identity_payload, dict) and identity_payload
            else CognitiveIdentity.create(capabilities=["decision_pipeline", "reflection"])
        )
        self._init_network_bridge()
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
        self._init_reflection_state()

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
        self.register_sleep_activity()
        if self.should_trigger_sleep_phase():
            self.save_state("reflection_state_pre_sleep.json")
            self.run_sleep_phase_reflection()
            self.save_state("reflection_state_post_sleep.json")
        return decision_record

    def run_simulation_cycle(self, scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run KPI simulation and feed results back into strategy evolution."""
        report = self.simulation_engine.run(scenarios)
        self.strategy_engine.ingest_simulation_feedback(report)
        self._apply_cognitive_update(
            actor="agent",
            action="canonical_update",
            key="last_simulation_metrics",
            value={
                "success_rate": report["success_rate"],
                "prediction_accuracy": report["prediction_accuracy"],
                "total_value": report["total_value"],
            },
        )
        return report

    def run_tool_healthchecks(self) -> Dict[str, Dict[str, Any]]:
        """Run active tool healthchecks and persist latest report."""
        return self.tool_runtime.run_active_healthchecks()

    def run_tool_healthcheck_cycle(self, active: bool = True, interval_s: float = 60.0) -> Dict[str, Any]:
        """Run scheduler-backed healthcheck cycle for compatibility with operator flows."""
        scheduler = ToolHealthcheckScheduler(self.tool_runtime, interval_s=interval_s)
        result = scheduler.run_once(active=active)
        normalized: Dict[str, bool] = {}
        for name, snapshot in result.get("tool_health", {}).items():
            if isinstance(snapshot, bool):
                normalized[name] = snapshot
            elif isinstance(snapshot, dict):
                normalized[name] = bool(snapshot.get("ok", snapshot.get("is_healthy", False)))
            else:
                normalized[name] = bool(snapshot)
        result["tool_health"] = normalized
        return result

    def reflect_and_propose(self) -> List[Dict[str, Any]]:
        """Generate reflection proposals from current cognitive state."""
        proposals = self.reflection_engine.generate_proposals(max_proposals=3)
        proposals.extend(self.generate_strategy_mutation_proposals())
        return proposals

    def register_sleep_activity(self, now: datetime | None = None) -> None:
        """Track activity count/time for sleep-phase scheduling."""
        event_time = now or datetime.now(timezone.utc)
        self._apply_cognitive_update(actor="agent", action="belief_update", key="last_action_at", value=event_time.isoformat())
        self._apply_cognitive_update(
            actor="agent",
            action="belief_update",
            key="actions_since_sleep",
            value=int(self.cognitive_state.get("actions_since_sleep", 0)) + 1,
        )

    def should_trigger_sleep_phase(self, now: datetime | None = None) -> bool:
        """Return True when reflection sleep-phase should run."""
        now_utc = now or datetime.now(timezone.utc)
        actions_since_sleep = int(self.cognitive_state.get("actions_since_sleep", 0))
        if actions_since_sleep >= 100:
            return True

        last_sleep_raw = self.cognitive_state.get("last_sleep_phase_at")
        if not isinstance(last_sleep_raw, str):
            return False
        last_sleep = datetime.fromisoformat(last_sleep_raw)
        return now_utc - last_sleep >= timedelta(hours=24)

    def run_sleep_phase_reflection(self, now: datetime | None = None) -> Dict[str, Any]:
        """Run automatic sleep-phase reflection cycle and save summary in state."""
        now_utc = now or datetime.now(timezone.utc)
        proposals = self.reflect_and_propose()
        summary = {
            "timestamp": now_utc.isoformat(),
            "proposal_count": len(proposals),
            "actions_since_sleep": int(self.cognitive_state.get("actions_since_sleep", 0)),
        }
        self._apply_cognitive_update(actor="agent", action="reflection_generated", key="last_sleep_phase_summary", value=summary)
        self._apply_cognitive_update(actor="agent", action="reflection_generated", key="last_sleep_phase_at", value=now_utc.isoformat())
        self._apply_cognitive_update(actor="agent", action="reflection_generated", key="actions_since_sleep", value=0)
        return summary

    def generate_strategy_mutation_proposals(self) -> List[Dict[str, Any]]:
        """Generate deterministic rule-based strategy mutation proposals."""
        mutation_rules = {
            "retrieve_context": ["retrieve_context_light", "retrieve_context_with_cache", "retrieve_context_topk"],
            "answer_with_tool": ["answer_with_tool_safe", "answer_with_tool_parallel", "answer_with_tool_retry"],
            "structured_reasoning": ["structured_reasoning_fast", "structured_reasoning_deep", "structured_reasoning_chain"],
        }
        strategy_stats = self.cognitive_state.get("strategy_stats", {})
        proposals: List[Dict[str, Any]] = []
        mutation_log = self.cognitive_state.setdefault("strategy_mutation_log", [])
        for base_action in strategy_stats:
            for idx, variant in enumerate(mutation_rules.get(base_action, []), start=1):
                proposal = {
                    "proposal_id": f"mutation:{base_action}:{idx}",
                    "change_type": "strategy_mutation",
                    "target": base_action,
                    "proposed_value": variant,
                    "confidence": 0.91 if idx == 1 else 0.72,
                    "reason": "rule_based_mutation",
                }
                proposals.append(proposal)
                mutation_log.append({"event": "generated", "proposal": proposal})
        return proposals

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
            "cognitive_timeline": self.cognitive_state.get("cognitive_timeline", [])[-50:],
            "cognitive_identity": self.cognitive_state.get("cognitive_identity", {}),
            "cognitive_network_outbox_size": len(self.cognitive_state.get("cognitive_network_outbox", [])),
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
        self._apply_cognitive_update(
            actor="agent",
            action="belief_update",
            key="pipeline_activity",
            value={
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": activity_type,
                "details": details or {},
            },
            operation="append",
        )


    def _init_reflection_state(self) -> None:
        """Ensure reflection-related persistence keys exist."""
        self.cognitive_state.setdefault("reflection_dashboard_log", [])
        self.cognitive_state.setdefault("strategy_mutation_log", [])
        self.cognitive_state.setdefault("actions_since_sleep", 0)
        self.cognitive_state.setdefault("cognitive_timeline", [])
        self.cognitive_state.setdefault("cognitive_identity", self.cognitive_identity.to_dict())
        self.cognitive_state.setdefault("cognitive_network_outbox", [])

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

    def _init_network_bridge(self) -> None:
        """Bridge local CTL events to LTP-like mesh envelopes for federation."""

        def _forward(tx: CognitiveTransaction) -> None:
            envelope = LTPEnvelope.from_transaction(
                tx=tx,
                sender=self.cognitive_identity.agent_id,
                receiver="mesh:broadcast",
                signing_key=self.cognitive_identity.public_key,
            )
            outbox = self.cognitive_state.setdefault("cognitive_network_outbox", [])
            outbox.append(envelope.to_dict())

        self.cognitive_event_mesh.subscribe(_forward)

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
        self._apply_cognitive_update(
            actor="agent",
            action="belief_update",
            key="action_log",
            value=decision_record,
            operation="append",
        )

    def _append_action_history(self, decision_record: Dict[str, Any]) -> None:
        """Append compact history records for long-term learning."""
        self._apply_cognitive_update(
            actor="agent",
            action="belief_update",
            key="action_history",
            value={
                "timestamp": decision_record["timestamp"],
                "action": decision_record["recommended_action"],
                "predicted_outcome": decision_record["predicted_outcome"],
                "actual_outcome": decision_record["actual_outcome"],
                "success": decision_record["success"],
                "outcome_value": decision_record["outcome_value"],
                "fallback_reason": decision_record.get("fallback_reason"),
            },
            operation="append",
        )

    def _update_metrics(self, decision_record: Dict[str, Any]) -> None:
        """Store baseline decision metrics in cognitive state."""
        self._apply_cognitive_update(
            actor="agent",
            action="belief_update",
            key="last_decision_metrics",
            value={
                "confidence": decision_record["confidence"],
                "calibrated_confidence": decision_record["calibrated_confidence"],
                "predicted_outcome": decision_record["predicted_outcome"],
                "action_success": decision_record["success"],
                "fallback_reason": decision_record.get("fallback_reason"),
            },
        )

    def _update_long_term_metrics(self) -> None:
        """Update simple long-term learning metrics from action history."""
        history = self.cognitive_state.get("action_history", [])
        if not history:
            return

        successes = sum(1 for item in history if item.get("success") is True)
        attempts = len(history)
        value_sum = sum(float(item.get("outcome_value", 0.0) or 0.0) for item in history)

        self._apply_cognitive_update(
            actor="agent",
            action="belief_update",
            key="long_term_metrics",
            value={
                "total_attempts": attempts,
                "success_rate": successes / attempts,
                "total_value": value_sum,
                "average_value": value_sum / attempts,
            },
        )


    def append_cognitive_transaction(self, tx: CognitiveTransaction) -> None:
        """Append external cognitive transaction and rebuild materialized state."""
        self.cognitive_transaction_log.append(tx)
        next_state = self.cognitive_reducer.apply(self.cognitive_state, tx)
        self.cognitive_state.clear()
        self.cognitive_state.update(next_state)
        self.cognitive_store.state = dict(self.cognitive_state)
        self.cognitive_store.cursor = self.cognitive_transaction_log.size()

    def _apply_cognitive_update(
        self,
        actor: str,
        action: str,
        key: str,
        value: Any,
        operation: str = "set",
    ) -> None:
        tx = CognitiveTransaction.create(
            actor=actor,
            action=action,
            payload={"op": operation, "key": key, "value": value},
        )
        self.cognitive_transaction_log.append(tx)
        next_state = self.cognitive_reducer.apply(self.cognitive_state, tx)
        self.cognitive_state.clear()
        self.cognitive_state.update(next_state)
        self.cognitive_store.state = dict(self.cognitive_state)
        self.cognitive_store.cursor = self.cognitive_transaction_log.size()
