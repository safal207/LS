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


def test_constitution_history_is_capped_to_500_rows(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    for i in range(520):
        store.store_constitution_evaluation(
            {
                "cycle_id": f"cx-{i}",
                "constitution": {"passed": True, "findings": []},
            }
        )
    rows = store.get_constitution_history(limit=1000)
    assert len(rows) == 500
    assert rows[0]["cycle_id"] == "cx-20"
    assert rows[-1]["cycle_id"] == "cx-519"


def test_council_action_history_is_capped_to_1000_rows(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    for i in range(1015):
        store.store_council_action_record(
            {
                "action_id": f"a-{i}",
                "action": "noop",
                "updates": [],
                "rolled_back": False,
            }
        )
    rows = store.get_council_action_history(limit=2000)
    assert len(rows) == 1000
    assert rows[0]["action_id"] == "a-15"
    assert rows[-1]["action_id"] == "a-1014"


def test_rollback_returns_not_found_for_unknown_action(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    result = store.rollback_council_action(action_id="missing")
    assert result["rolled_back"] is False
    assert result["reason"] == "action_not_found"


def test_rollback_reports_partial_scope_when_unsupported_updates_present(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    store.store_council_action_record(
        {
            "action_id": "a-partial",
            "action": "expand_core_nodes_window",
            "updates": [
                {
                    "update_type": "window_expand",
                    "before": 25,
                    "after": 30,
                }
            ],
            "rolled_back": False,
        }
    )
    result = store.rollback_council_action(action_id="a-partial")
    assert result["rolled_back"] is False
    assert result["partially_rolled_back"] is True
    assert result["rollback_scope"] == "partial"
    assert result["reason"] == "partial_rollback_unsupported_updates"
    row = store.get_council_action_history(limit=1)[0]
    assert row["rolled_back"] is False
    assert row["partially_rolled_back"] is True
    assert row["rollback_scope"] == "partial"
    assert row["rollback_reason"] == "partial_rollback_unsupported_updates"
