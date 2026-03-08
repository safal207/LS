from modules.orientation.cognitive_state import CognitiveStateCenter
from modules.coordinator.coordinator import Coordinator


def test_cognitive_state_center_snapshot_restore_and_diff() -> None:
    center = CognitiveStateCenter(max_snapshots=4)
    first = center.update_state(
        create_snapshot=True,
        beliefs=[{"id": "b1"}],
        causal_edges=[{"from": "b1", "to": "b2"}],
        temporal_nodes=[{"id": "t1"}],
        mission_state={"goal": "assist"},
        cot_trace=[{"role": "user", "content": "hi"}],
    )
    second = center.update_state(
        create_snapshot=True,
        beliefs=[{"id": "b1"}, {"id": "b2"}],
        temporal_nodes=[{"id": "t1"}, {"id": "t2"}],
        mission_state={"goal": "assist", "phase": "thinking"},
    )

    diff = center.diff_cognitive_snapshots(first, second)
    assert diff["beliefs_delta"] == 1
    assert diff["temporal_nodes_delta"] == 1
    assert diff["mission_state_changed"] is True

    restored = center.restore_cognitive_snapshot(snapshot_id=first["snapshot_id"])
    assert restored["state"]["mission_state"]["goal"] == "assist"
    assert len(restored["state"]["beliefs"]) == 1


def test_coordinator_exposes_cognitive_snapshot_api() -> None:
    coordinator = Coordinator()
    payload = coordinator.decide(
        "test input",
        context={"mission_state": {"goal": "x"}, "cot_trace": [{"role": "user", "content": "q"}]},
        telemetry={"diversity": 0.4},
        retrospective={"beliefs": [{"id": "b1"}], "temporal_nodes": [{"id": "t1"}]},
    )

    snapshot = payload.get("cognitive_snapshot")
    assert isinstance(snapshot, dict)
    assert snapshot["state"]["mission_state"]["goal"] == "x"

    coordinator.record_outcome({"success": False})
    latest = coordinator.get_cognitive_snapshot()
    assert "trajectory_error" in latest["state"]["mission_state"]
