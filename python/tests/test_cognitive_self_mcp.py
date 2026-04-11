from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ls.agent_shell.cognitive_state import CognitiveStateBridge
from modules.graph.memory_store import MemoryGraphStore
from modules.graph.models import ResonanceKnowledgeUnit


class _FakeRuntime:
    pass


def test_ask_self_parses_numeric_days_and_reports_delta(tmp_path, monkeypatch):
    store_path = tmp_path / "cases.jsonl"
    monkeypatch.setenv("GRAPH_MEMORY_STORE_PATH", str(store_path))
    store = MemoryGraphStore(store_path)
    store.store_resonance_unit(
        ResonanceKnowledgeUnit(
            source_question="focus",
            resonance_score=0.9,
            alignment_score=0.8,
        )
    )

    # Seed explicit coherence history rows across dates.
    now = datetime.now(timezone.utc)
    rows = [
        {
            "timestamp": (now - timedelta(days=2)).isoformat(),
            "coherence_score": 0.40,
            "source": "test",
            "cycle_id": "c-1",
        },
        {
            "timestamp": (now - timedelta(hours=3)).isoformat(),
            "coherence_score": 0.70,
            "source": "test",
            "cycle_id": "c-2",
        },
    ]
    store._atomic_write_jsonl(store._coherence_history_path(), rows)  # noqa: SLF001

    bridge = CognitiveStateBridge(task_manager=_FakeRuntime())
    result = bridge.ask_self("как ты изменился за последние 3 дня?")

    assert result["question"].startswith("как ты")
    assert result["coherence_delta"] > 0
    assert "3" in result["answer"]


def test_get_cognitive_state_backward_compatible_shape(tmp_path, monkeypatch):
    store_path = tmp_path / "cases.jsonl"
    monkeypatch.setenv("GRAPH_MEMORY_STORE_PATH", str(store_path))
    bridge = CognitiveStateBridge(task_manager=_FakeRuntime())

    payload = bridge.get_cognitive_state(top_k=5, min_resonance_score=0.2)

    assert payload["resource"] == "cognitive/state"
    assert "resonance_snapshot" in payload
    assert "relational_state" in payload
    assert "alignment" in payload
    assert "omni" in payload
