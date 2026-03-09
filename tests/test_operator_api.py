from agent.decision_pipeline import DecisionPipeline
from agent.operator_api import AgentOperatorAPI


def test_operator_api_get_snapshot_returns_pipeline_snapshot() -> None:
    state = {
        "strategy_stats": {"answer_with_tool": {"attempts": 2, "successes": 1, "total_value": 0.5}},
    }
    api = AgentOperatorAPI(DecisionPipeline(state))

    snapshot = api.get_agent_snapshot()

    assert "flow" in snapshot
    assert "controls" in snapshot


def test_operator_api_get_replay_clamps_limit() -> None:
    state = {
        "action_log": [
            {"timestamp": "t1", "recommended_action": "a1"},
            {"timestamp": "t2", "recommended_action": "a2"},
        ]
    }
    api = AgentOperatorAPI(DecisionPipeline(state))

    replay = api.get_agent_replay(limit=0)

    assert replay["limit"] == 1
    assert len(replay["replay"]) == 1


def test_operator_api_post_controls_updates_pipeline_controls() -> None:
    state = {}
    api = AgentOperatorAPI(DecisionPipeline(state))

    response = api.post_agent_controls(
        {
            "low_confidence_threshold": 0.42,
            "fallback_action": "answer_directly",
            "tool_failure_fallback_action": "retrieve_context",
        }
    )

    assert response["status"] == "ok"
    assert response["controls"]["low_confidence_threshold"] == 0.42
    assert response["controls"]["fallback_action"] == "answer_directly"
    assert response["controls"]["tool_failure_fallback_action"] == "retrieve_context"
