import threading

from modules.agent.loop import AgentLoop


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
    assert "mission_state" in state
