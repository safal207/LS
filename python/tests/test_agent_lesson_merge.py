import threading

from modules.agent.lessons import evaluate_external_lesson_for_merge
from modules.agent.loop import AgentLoop


def test_evaluate_external_lesson_accepts_high_quality_and_resonance() -> None:
    result = evaluate_external_lesson_for_merge(
        {"id": "l1", "content": "optimize memory cache strategy", "quality": 0.9},
        existing_beliefs=[{"id": "b1", "content": "memory cache strategy for performance"}],
    )

    assert result.decision == "accept"
    assert result.score_breakdown["final_score"] >= 0.65


def test_evaluate_external_lesson_rejects_low_quality() -> None:
    result = evaluate_external_lesson_for_merge(
        {"id": "l2", "content": "noise", "quality": 0.1},
        existing_beliefs=[{"id": "b1", "content": "useful strategy"}],
    )

    assert result.decision == "reject"


def test_agent_loop_merge_external_lesson_emits_event_and_updates_state_on_accept() -> None:
    captured = []
    loop = AgentLoop(handler=lambda q: "ok", on_event=lambda e: captured.append((e.type, e.payload)))
    cancel = threading.Event()
    loop._set_active(42, cancel, None)

    payload = loop.merge_external_lesson(
        {"id": "l-ok", "content": "cache latency optimization lesson", "quality": 0.95},
        task_id=42,
    )

    assert payload["decision"] == "accept"
    assert payload["merged"] is True
    assert any(kind == "lesson_merged" for kind, _ in captured)

    snapshot = loop.get_cognitive_snapshot()
    belief_ids = [belief.get("id") for belief in snapshot["state"].get("beliefs", []) if isinstance(belief, dict)]
    assert "l-ok" in belief_ids


def test_agent_loop_merge_external_lesson_defer_or_reject_without_state_change() -> None:
    loop = AgentLoop(handler=lambda q: "ok")
    before = loop.get_cognitive_snapshot()

    payload = loop.merge_external_lesson({"id": "l-bad", "content": "", "quality": 0.1})

    assert payload["decision"] in {"defer", "reject"}
    assert payload["merged"] is False
    after = loop.get_cognitive_snapshot()
    assert len(after["state"].get("beliefs", [])) == len(before["state"].get("beliefs", []))
