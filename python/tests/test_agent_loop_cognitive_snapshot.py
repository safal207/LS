import threading

from modules.agent.loop import AgentLoop
from modules.agent.reconstruction import reconstruct_cognitive_state_at_timestamp, reconstruct_cognitive_state_from_events


def test_agent_loop_snapshot_restore_api() -> None:
    loop = AgentLoop(handler=lambda q: f"echo:{q}")

    loop._remember_question("hello")
    snap_a = loop.get_cognitive_snapshot()
    loop._remember_answer("world", 0.1)
    snap_b = loop.get_cognitive_snapshot()

    diff = loop.diff_cognitive_snapshots(snap_a, snap_b)
    assert diff["mission_state_changed"] is False

    restored = loop.restore_cognitive_snapshot(payload=snap_a)
    assert isinstance(restored, dict)


def test_agent_loop_process_updates_snapshot() -> None:
    loop = AgentLoop(handler=lambda q: "ok")
    cancel = threading.Event()

    loop._set_active(1, cancel, None)
    loop._process_item({"type": "question", "text": "hi"}, 1, cancel)

    snapshot = loop.get_cognitive_snapshot()
    state = snapshot["state"]
    assert isinstance(state.get("cot_trace"), list)
    if state["cot_trace"]:
        assert "content_chars" in state["cot_trace"][0]
        assert "content" not in state["cot_trace"][0]
    assert "mission_state" in state


def test_agent_loop_emits_cognitive_events() -> None:
    events = []
    loop = AgentLoop(handler=lambda q: "ok", on_event=lambda e: events.append(e.type))
    cancel = threading.Event()

    loop._set_active(7, cancel, None)
    loop._process_item({"type": "question", "text": "hi"}, 7, cancel)

    assert "cognitive_state_updated" in events
    snap = loop.get_cognitive_snapshot()
    loop.restore_cognitive_snapshot(payload=snap)
    assert "cognitive_snapshot_restored" in events


class _CaptureSink:
    def __init__(self) -> None:
        self.events = []

    def emit(self, event):
        self.events.append(event)


def test_reconstruct_cognitive_state_from_observability_events() -> None:
    sink = _CaptureSink()
    loop = AgentLoop(handler=lambda q: "ok", event_sink=sink, observability_enabled=True)
    cancel = threading.Event()

    loop._set_active(11, cancel, None)
    loop._process_item({"type": "question", "text": "hi"}, 11, cancel)
    current = loop.get_cognitive_snapshot()
    loop.restore_cognitive_snapshot(payload=current)

    reconstructed = reconstruct_cognitive_state_from_events(sink.events)
    assert isinstance(reconstructed["timeline"], list)
    assert len(reconstructed["timeline"]) >= 2
    assert "mission_state" in reconstructed["state"]
    assert reconstructed["state"]["mission_state"].get("causal_memory_backend") in {"rust", "python_fallback"}

    first_cognitive = next(event for event in sink.events if event.get("type") == "cognitive_state")
    at_first = reconstruct_cognitive_state_at_timestamp(sink.events, float(first_cognitive["timestamp"]))
    assert len(at_first["timeline"]) == 1


def test_reconstruct_cognitive_state_sorts_events_by_timestamp_and_copies_state() -> None:
    events = [
        {
            "type": "cognitive_state",
            "timestamp": 2.0,
            "task_id": "t1",
            "payload": {"snapshot_id": "s2", "state": {"mission_state": {"step": 2}}},
        },
        {
            "type": "cognitive_state",
            "timestamp": 1.0,
            "task_id": "t1",
            "payload": {"snapshot_id": "s1", "state": {"mission_state": {"step": 1}}},
        },
    ]

    reconstructed = reconstruct_cognitive_state_from_events(events)
    assert [point["snapshot_id"] for point in reconstructed["timeline"]] == ["s1", "s2"]
    assert reconstructed["state"]["mission_state"]["step"] == 2

    events[0]["payload"]["state"]["mission_state"]["step"] = 999
    assert reconstructed["state"]["mission_state"]["step"] == 2
