from agent.observability import DecisionObservability


def test_observability_session_replay_limit_and_order() -> None:
    state = {
        "action_log": [
            {"timestamp": "t1", "recommended_action": "a1", "predicted_outcome": "p1", "actual_outcome": "o1", "success": True},
            {"timestamp": "t2", "recommended_action": "a2", "predicted_outcome": "p2", "actual_outcome": "o2", "success": False, "fallback_reason": "tool_error"},
            {"timestamp": "t3", "recommended_action": "a3", "predicted_outcome": "p3", "actual_outcome": "o3", "success": True},
        ]
    }
    obs = DecisionObservability(state)

    replay = obs.get_session_replay(limit=2)

    assert len(replay) == 2
    assert replay[0]["timestamp"] == "t2"
    assert replay[1]["recommended_action"] == "a3"


def test_observability_trend_summary_computes_rates() -> None:
    state = {
        "action_log": [
            {"timestamp": "t1", "success": True, "confidence": 0.9, "fallback_reason": None},
            {"timestamp": "t2", "success": False, "confidence": 0.8, "fallback_reason": "tool_error"},
            {"timestamp": "t3", "success": True, "confidence": 0.6, "fallback_reason": None},
        ]
    }
    obs = DecisionObservability(state)

    trend = obs.get_trend_summary(window=3)

    assert trend["decision_count"] == 3
    assert trend["success_rate"] == 2 / 3
    assert trend["fallback_rate"] == 1 / 3
    assert trend["calibration_error"] >= 0.0
