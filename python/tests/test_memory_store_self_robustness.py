from __future__ import annotations

from modules.graph.memory_store import MemoryGraphStore


def test_get_constitution_history_skips_malformed_rows(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    path = store._constitution_history_path()  # noqa: SLF001
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"cycle_id":"ok-1","constitution":{"passed":true}}\n'
        '{bad-json\n'
        '{"cycle_id":"ok-2","constitution":{"passed":false}}\n',
        encoding="utf-8",
    )

    rows = store.get_constitution_history(limit=10)
    assert len(rows) == 2
    assert rows[0]["cycle_id"] == "ok-1"
    assert rows[1]["cycle_id"] == "ok-2"


def test_get_council_action_history_skips_malformed_rows(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    path = store._council_action_history_path()  # noqa: SLF001
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"action_id":"a1","action":"x"}\n'
        'oops\n'
        '{"action_id":"a2","action":"y"}\n',
        encoding="utf-8",
    )

    rows = store.get_council_action_history(limit=10)
    assert len(rows) == 2
    assert rows[0]["action_id"] == "a1"
    assert rows[1]["action_id"] == "a2"
