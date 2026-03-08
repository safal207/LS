from modules.agent.dashboard import build_cognitive_dashboard, render_cognitive_dashboard
from modules.agent.event_schema import build_observability_event


def _event(ts: float, snapshot_id: str, beliefs: int, confidence: float) -> dict:
    return {
        "type": "cognitive_state",
        "timestamp": ts,
        "task_id": "t1",
        "version": "1.0",
        "state": "active",
        "payload": {
            "snapshot_id": snapshot_id,
            "state": {
                "beliefs": [{"id": f"b{i}", "weight": 0.5 + i} for i in range(beliefs)],
                "causal_edges": [{"from": "a", "to": "b"}],
                "temporal_nodes": [{"id": "n1"}],
                "mission_state": {
                    "confidence": confidence,
                    "adaptive_bias": 0.2,
                    "trajectory_error": 0.1,
                },
                "cot_trace": [{"role": "user", "content_chars": 8, "content_present": True}],
            },
            "diff": {},
        },
    }


def test_build_cognitive_dashboard_summary_and_timeline() -> None:
    events = [_event(1.0, "s1", 1, 0.4), _event(2.0, "s2", 3, 0.7)]

    dashboard = build_cognitive_dashboard(events, last_n=10)

    assert dashboard["events_analyzed"] == 2
    assert dashboard["current"]["snapshot_id"] == "s2"
    assert dashboard["current"]["beliefs"] == 3
    assert dashboard["belief_weights"]["count"] == 3
    assert len(dashboard["timeline"]) == 2
    assert dashboard["timeline"][-1]["confidence"] == 0.7
    assert dashboard["timeline"][-1]["delta"]["beliefs"] == 2


def test_build_cognitive_dashboard_respects_last_n_window() -> None:
    events = [_event(1.0, "s1", 1, 0.4), _event(2.0, "s2", 2, 0.6), _event(3.0, "s3", 4, 0.8)]

    dashboard = build_cognitive_dashboard(events, last_n=2)

    assert dashboard["events_analyzed"] == 2
    assert dashboard["current"]["snapshot_id"] == "s3"
    assert dashboard["timeline"][0]["snapshot_id"] == "s2"


def test_render_cognitive_dashboard_text() -> None:
    dashboard = build_cognitive_dashboard([_event(1.0, "s1", 1, 0.4), _event(2.0, "s2", 2, 0.5)])
    rendered = render_cognitive_dashboard(dashboard)

    assert "Cognitive Dashboard" in rendered
    assert "snapshot_id: s2" in rendered
    assert "beliefs: 2" in rendered
    assert "last_delta:" in rendered


def test_observability_schema_supports_snapshot_restored_and_lesson_merged() -> None:
    restored = build_observability_event(
        "snapshot_restored",
        {"snapshot_id": "s1"},
        "active",
        "task-1",
        timestamp=1.0,
    )
    assert restored is not None
    assert restored["type"] == "cognitive_state"

    lesson = build_observability_event(
        "lesson_merged",
        {"lesson_id": "l1"},
        "active",
        "task-1",
        timestamp=2.0,
    )
    assert lesson is not None
    assert lesson["type"] == "learning"
