import pytest
from agent.decision_pipeline import DecisionPipeline


def test_pipeline_selects_high_confidence_action_and_logs_metrics() -> None:
    state = {
        "causal_edges": [
            {"cause": "answer_with_tool", "effect": "high_quality_answer", "confidence": 0.9},
            {"cause": "retrieve_context", "effect": "partial_context", "confidence": 0.4},
        ]
    }
    pipeline = DecisionPipeline(state)
    events = [{"type": "decision", "value": "answer_directly"}]

    result = pipeline.run(events, actual_outcome="high_quality_answer", success=True, outcome_value=0.8)

    assert result["recommended_action"] == "answer_with_tool"
    assert result["predicted_outcome"] == "high_quality_answer"
    assert result["confidence"] == 0.9
    assert state["last_decision_metrics"] == {
        "confidence": 0.9,
        "calibrated_confidence": 0.9,
        "predicted_outcome": "high_quality_answer",
        "action_success": True,
        "fallback_reason": None,
    }
    assert len(state["action_log"]) == 1
    assert len(state["action_history"]) == 1
    assert state["strategy_stats"]["answer_with_tool"]["attempts"] == 1
    assert state["strategy_stats"]["answer_with_tool"]["successes"] == 1


def test_pipeline_resolves_conflict_using_historical_success() -> None:
    state = {
        "causal_edges": [
            {"cause": "answer_with_tool", "effect": "tool_answer", "confidence": 0.75},
            {"cause": "retrieve_context", "effect": "retrieved_answer", "confidence": 0.8},
        ],
        "strategy_stats": {
            "answer_with_tool": {"attempts": 10, "successes": 10, "total_value": 8.0},
            "retrieve_context": {"attempts": 10, "successes": 2, "total_value": 1.0},
        },
    }
    pipeline = DecisionPipeline(state)
    events = [{"type": "decision", "value": "answer_directly"}]

    result = pipeline.run(events)

    assert result["recommended_action"] == "answer_with_tool"
    assert result["ranked_strategies"][0]["action"] == "answer_with_tool"


def test_pipeline_uses_fallback_on_low_confidence() -> None:
    state = {"causal_edges": []}
    pipeline = DecisionPipeline(state, low_confidence_threshold=0.2, fallback_action="retrieve_context")
    events = [{"type": "decision", "value": "answer_directly"}]

    result = pipeline.run(events)

    assert result["recommended_action"] == "retrieve_context"
    assert result["predicted_outcome"] == "unknown"
    assert result["confidence"] == 0.0
    assert state["last_decision_metrics"]["predicted_outcome"] == "unknown"


def test_pipeline_calibrates_overestimated_strategy_and_tracks_long_term_metrics() -> None:
    state = {
        "causal_edges": [
            {"cause": "answer_with_tool", "effect": "tool_answer", "confidence": 0.95},
            {"cause": "retrieve_context", "effect": "retrieved_answer", "confidence": 0.7},
        ],
        "strategy_stats": {
            "answer_with_tool": {"attempts": 8, "successes": 1, "total_value": 0.8, "overestimation_events": 0},
            "retrieve_context": {"attempts": 8, "successes": 6, "total_value": 4.8, "overestimation_events": 0},
        },
    }
    pipeline = DecisionPipeline(state)
    events = [{"type": "decision", "value": "answer_directly"}]

    result = pipeline.run(events, actual_outcome="retrieved_answer", success=True, outcome_value=0.6)

    assert result["recommended_action"] == "retrieve_context"
    assert state["strategy_stats"]["answer_with_tool"]["overestimation_events"] >= 1
    assert state["long_term_metrics"]["total_attempts"] == 1
    assert state["long_term_metrics"]["total_value"] == 0.6


def test_pipeline_executes_tool_action_and_records_audit() -> None:
    state = {
        "causal_edges": [
            {"cause": "answer_with_tool", "effect": "high_quality_answer", "confidence": 0.95},
            {"cause": "retrieve_context", "effect": "context_answer", "confidence": 0.3},
        ]
    }

    def answer_with_tool(payload: dict) -> dict:
        return {"answer": "42", "events": len(payload.get("event_sequence", []))}

    pipeline = DecisionPipeline(state, tool_registry={"answer_with_tool": answer_with_tool})
    events = [{"type": "decision", "value": "answer_directly"}]

    result = pipeline.run(events, success=True, outcome_value=1.0)

    assert result["recommended_action"] == "answer_with_tool"
    assert result["tool_execution"] is not None
    assert result["tool_execution"]["status"] == "ok"
    assert result["tool_execution"]["result"]["answer"] == "42"
    assert state["tool_audit_log"][-1]["status"] == "ok"


def test_pipeline_tool_error_uses_audit_and_health_tracking() -> None:
    state = {
        "causal_edges": [
            {"cause": "answer_with_tool", "effect": "high_quality_answer", "confidence": 0.95},
            {"cause": "retrieve_context", "effect": "context_answer", "confidence": 0.3},
        ]
    }

    def broken_tool(payload: dict) -> dict:
        raise RuntimeError("downstream unavailable")

    pipeline = DecisionPipeline(state, tool_registry={"answer_with_tool": broken_tool})
    events = [{"type": "decision", "value": "answer_directly"}]

    result = pipeline.run(events)

    assert result["recommended_action"] == "structured_reasoning"
    assert result["fallback_reason"] == "tool_error"
    assert result["tool_execution"]["status"] == "error"
    assert "downstream unavailable" in result["tool_execution"]["error"]
    assert state["tool_health"]["answer_with_tool"]["is_healthy"] is False


def test_pipeline_updates_existing_causal_edge_confidence_from_success() -> None:
    state = {
        "causal_edges": [
            {"cause": "answer_with_tool", "effect": "high_quality_answer", "confidence": 0.6},
            {"cause": "retrieve_context", "effect": "context_answer", "confidence": 0.4},
        ]
    }

    def answer_with_tool(payload: dict) -> dict:
        return {"ok": True}

    pipeline = DecisionPipeline(state, tool_registry={"answer_with_tool": answer_with_tool})
    events = [{"type": "decision", "value": "answer_directly"}]

    pipeline.run(events, actual_outcome="high_quality_answer", success=True)

    updated = next(e for e in state["causal_edges"] if e["cause"] == "answer_with_tool" and e["effect"] == "high_quality_answer")
    assert updated["confidence"] > 0.6


def test_pipeline_creates_new_causal_edge_from_feedback() -> None:
    state = {
        "causal_edges": [
            {"cause": "answer_with_tool", "effect": "high_quality_answer", "confidence": 0.8},
        ]
    }

    pipeline = DecisionPipeline(state)
    events = [{"type": "decision", "value": "answer_directly"}]

    pipeline.run(events, actual_outcome="novel_outcome", success=True)

    assert any(
        e["cause"] == "answer_with_tool" and e["effect"] == "novel_outcome"
        for e in state["causal_edges"]
    )


def test_pipeline_simulation_cycle_updates_metrics_and_strategy_stats() -> None:
    state = {
        "causal_edges": [
            {"cause": "answer_with_tool", "effect": "good", "confidence": 0.7},
        ]
    }
    pipeline = DecisionPipeline(state)

    report = pipeline.run_simulation_cycle(
        [
            {
                "action": "answer_with_tool",
                "predicted_outcome": "good",
                "actual_outcome": "good",
                "success": True,
                "outcome_value": 0.8,
            },
            {
                "action": "retrieve_context",
                "predicted_outcome": "ok",
                "actual_outcome": "ok",
                "success": True,
                "outcome_value": 0.6,
            },
        ]
    )

    assert report["scenario_count"] == 2
    assert state["last_simulation_metrics"]["success_rate"] == 1.0
    assert state["strategy_stats"]["answer_with_tool"]["attempts"] >= 1
    assert state["strategy_stats"]["retrieve_context"]["successes"] >= 1


def test_pipeline_visualization_snapshot_and_controls_update() -> None:
    state = {
        "strategy_stats": {
            "answer_with_tool": {"attempts": 4, "successes": 3, "total_value": 2.0},
            "retrieve_context": {"attempts": 2, "successes": 1, "total_value": 0.6},
        },
        "last_decision_metrics": {"confidence": 0.7},
        "last_simulation_metrics": {"success_rate": 0.8},
    }
    pipeline = DecisionPipeline(state)
    pipeline.update_controls(low_confidence_threshold=0.4, fallback_action="answer_directly")

    snapshot = pipeline.get_visualization_snapshot()

    assert snapshot["controls"]["low_confidence_threshold"] == 0.4
    assert snapshot["controls"]["fallback_action"] == "answer_directly"
    assert snapshot["flow"].startswith("event -> counterfactuals")
    assert snapshot["heatmap"][0]["action"] == "answer_with_tool"


def test_pipeline_disables_tool_action_by_policy() -> None:
    state = {
        "causal_edges": [
            {"cause": "answer_with_tool", "effect": "high_quality_answer", "confidence": 0.95},
        ]
    }

    def answer_with_tool(payload: dict) -> dict:
        return {"answer": "42"}

    pipeline = DecisionPipeline(
        state,
        tool_registry={"answer_with_tool": answer_with_tool},
        allowed_tool_actions={"retrieve_context"},
    )
    events = [{"type": "decision", "value": "answer_directly"}]

    result = pipeline.run(events)

    assert result["recommended_action"] == "answer_with_tool"
    assert result["tool_execution"] is None


def test_pipeline_visualization_snapshot_includes_tool_fallback_control() -> None:
    state = {"strategy_stats": {"answer_with_tool": {"attempts": 1, "successes": 1, "total_value": 0.9}}}
    pipeline = DecisionPipeline(state)

    snapshot = pipeline.get_visualization_snapshot()

    assert snapshot["controls"]["tool_failure_fallback_action"] == "structured_reasoning"


def test_pipeline_session_replay_and_trends_in_snapshot() -> None:
    state = {
        "causal_edges": [
            {"cause": "answer_with_tool", "effect": "good", "confidence": 0.9},
        ]
    }

    def tool(payload: dict) -> dict:
        return {"ok": True}

    pipeline = DecisionPipeline(state, tool_registry={"answer_with_tool": tool})
    events = [{"type": "decision", "value": "answer_directly"}]

    pipeline.run(events, actual_outcome="good", success=True, outcome_value=0.8)
    pipeline.run(events, actual_outcome="bad", success=False, outcome_value=0.1)

    replay = pipeline.get_session_replay(limit=1)
    snapshot = pipeline.get_visualization_snapshot()

    assert len(replay) == 1
    assert replay[0]["actual_outcome"] == "bad"
    assert snapshot["trends"]["decision_count"] >= 2
    assert "success_rate" in snapshot["trends"]


def test_pipeline_evaluate_strategy_candidate_persists_gate_history() -> None:
    state = {}
    pipeline = DecisionPipeline(state)

    gate = pipeline.evaluate_strategy_candidate(
        candidate_metrics={"success_rate": 0.8, "prediction_accuracy": 0.72, "average_value": 0.5},
        baseline_metrics={"success_rate": 0.7, "prediction_accuracy": 0.73, "average_value": 0.4},
    )

    assert gate["accepted"] is True
    assert gate["accepted_by_policy"] is True
    assert len(state["strategy_gate_history"]) == 1
    assert state["last_strategy_gate"]["deltas"]["success_rate_delta"] == pytest.approx(0.1)


def test_pipeline_evaluate_strategy_candidate_supports_manual_override() -> None:
    state = {}
    pipeline = DecisionPipeline(state)

    gate = pipeline.evaluate_strategy_candidate(
        candidate_metrics={"success_rate": 0.6, "prediction_accuracy": 0.5, "average_value": 0.2},
        baseline_metrics={"success_rate": 0.7, "prediction_accuracy": 0.7, "average_value": 0.3},
        manual_override_reason="business-critical experiment",
    )

    assert gate["accepted_by_policy"] is False
    assert gate["accepted"] is True
    assert gate["manual_override_reason"] == "business-critical experiment"


def test_pipeline_promote_strategy_candidate_rejects_when_gate_fails() -> None:
    state = {}
    pipeline = DecisionPipeline(state)

    result = pipeline.promote_strategy_candidate(
        candidate_strategy={"id": "s1", "name": "strategy-one"},
        candidate_metrics={"success_rate": 0.5, "prediction_accuracy": 0.5, "average_value": 0.2},
        baseline_metrics={"success_rate": 0.7, "prediction_accuracy": 0.7, "average_value": 0.3},
    )

    assert result["promotion_status"] == "rejected"
    assert state["strategy_promotion_history"][-1]["strategy_id"] == "s1"
    assert "active_strategy" not in state


def test_pipeline_promote_strategy_candidate_promotes_on_manual_override() -> None:
    state = {}
    pipeline = DecisionPipeline(state)

    result = pipeline.promote_strategy_candidate(
        candidate_strategy={"id": "s2", "name": "strategy-two", "action": "answer_with_tool"},
        candidate_metrics={"success_rate": 0.4, "prediction_accuracy": 0.4, "average_value": 0.1},
        baseline_metrics={"success_rate": 0.7, "prediction_accuracy": 0.7, "average_value": 0.3},
        manual_override_reason="urgent product requirement",
    )

    assert result["promotion_status"] == "promoted"
    assert state["active_strategy"]["id"] == "s2"
    assert state["promoted_strategies"][-1]["manual_override_reason"] == "urgent product requirement"


def test_pipeline_executes_registered_tool_adapter() -> None:
    from agent.tool_runtime import InMemoryDataToolAdapter

    state = {
        "causal_edges": [
            {"cause": "answer_with_tool", "effect": "high_quality_answer", "confidence": 0.95},
        ]
    }
    adapter = InMemoryDataToolAdapter("answer_with_tool", state)
    pipeline = DecisionPipeline(state, tool_adapters={"answer_with_tool": adapter})

    result = pipeline.run([{"type": "decision", "value": "answer_directly"}])

    assert result["recommended_action"] == "answer_with_tool"
    assert result["tool_execution"]["status"] == "ok"
