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
