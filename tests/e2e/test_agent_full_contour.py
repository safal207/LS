from agent.decision_pipeline import DecisionPipeline
from agent.operator_api import AgentOperatorAPI
from agent.tool_adapters import DataAdapter, HTTPContextAdapter


def test_agent_full_contour_smoke() -> None:
    state = {
        "causal_edges": [
            {"cause": "retrieve_context", "effect": "high_quality_answer", "confidence": 0.95},
        ]
    }

    def fake_http_client(**kwargs):
        if kwargs["path"] == "/health":
            return {"ok": True}
        return {"ok": True, "context": "ctx"}

    pipeline = DecisionPipeline(
        state,
        tool_adapters={
            "retrieve_context": HTTPContextAdapter(base_url="http://example.local", http_client=fake_http_client),
            "data_adapter": DataAdapter(),
        },
        allowed_tool_actions={"retrieve_context"},
    )
    api = AgentOperatorAPI(pipeline)

    # health scheduler + snapshot
    health = pipeline.run_tool_healthcheck_cycle(active=True)
    snap = api.get_agent_snapshot()
    assert health["tool_health"]["retrieve_context"] is True
    assert "tool_health" in snap

    # decision -> tool runtime -> observability
    decision = pipeline.run(
        [{"type": "decision", "value": "need_context"}],
        actual_outcome="high_quality_answer",
        success=True,
        outcome_value=1.0,
    )
    assert decision["tool_execution"]["status"] == "ok"

    replay = api.get_agent_replay(limit=5)
    assert len(replay["replay"]) >= 1

    # controls
    controls = api.post_agent_controls({"low_confidence_threshold": 0.33})
    assert controls["controls"]["low_confidence_threshold"] == 0.33

    # strategy gate / promote lifecycle
    promotion = pipeline.promote_strategy_candidate(
        candidate_strategy={"id": "e2e-s1", "name": "e2e"},
        candidate_metrics={"success_rate": 0.8, "prediction_accuracy": 0.8, "average_value": 0.8},
        baseline_metrics={"success_rate": 0.7, "prediction_accuracy": 0.7, "average_value": 0.7},
    )
    assert promotion["promotion_status"] == "promoted"
    assert state["active_strategy"]["id"] == "e2e-s1"

    # observability trend includes tool_kpi
    trends = pipeline.get_visualization_snapshot()["trends"]
    assert "tool_kpi" in trends
