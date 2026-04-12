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
    assert "day(s)" in result["answer"]
    assert "top_change_drivers" in result
    assert "causal_trace" in result


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


def test_get_constitution_status_returns_latest(tmp_path, monkeypatch):
    store_path = tmp_path / "cases.jsonl"
    monkeypatch.setenv("GRAPH_MEMORY_STORE_PATH", str(store_path))
    store = MemoryGraphStore(store_path)
    store.store_constitution_evaluation(
        {
            "cycle_id": "cx-10",
            "mode": "self-preservation",
            "constitution": {"passed": False, "findings": []},
            "blocked": True,
        }
    )
    bridge = CognitiveStateBridge(task_manager=_FakeRuntime())
    status = bridge.get_constitution_status(limit=5)
    assert status["resource"] == "self/constitution-status"
    assert status["latest"]["cycle_id"] == "cx-10"


def test_get_self_metrics_returns_snapshot(tmp_path, monkeypatch):
    store_path = tmp_path / "cases.jsonl"
    monkeypatch.setenv("GRAPH_MEMORY_STORE_PATH", str(store_path))
    store = MemoryGraphStore(store_path)
    store.store_constitution_evaluation(
        {
            "cycle_id": "cx-m1",
            "mode": "self-preservation",
            "constitution": {"passed": False, "findings": []},
            "policy_decision": {"allow_auto_apply": False, "reason": "blocked_by_preservation"},
        }
    )
    store.store_constitution_evaluation(
        {
            "cycle_id": "cx-m2",
            "mode": "self-preservation",
            "constitution": {"passed": True, "findings": []},
            "policy_decision": {"allow_auto_apply": True, "reason": "safe_for_auto_apply"},
        }
    )
    store.store_council_action_record(
        {
            "action_id": "a-1",
            "action": "increase_reinforcing_edge_strength",
            "updates": [],
            "rolled_back": False,
        }
    )
    bridge = CognitiveStateBridge(task_manager=_FakeRuntime())
    metrics = bridge.get_self_metrics(window=20)
    assert metrics["resource"] == "self/metrics"
    assert "metrics" in metrics
    assert "auto_action_apply_rate" in metrics["metrics"]
    assert "mean_recovery_cycles" in metrics["metrics"]
    assert metrics["metrics"]["mean_recovery_cycles"] >= 1.0


def test_action_history_and_rollback_bridge(tmp_path, monkeypatch):
    store_path = tmp_path / "cases.jsonl"
    monkeypatch.setenv("GRAPH_MEMORY_STORE_PATH", str(store_path))
    store = MemoryGraphStore(store_path)
    store.store_council_action_record(
        {
            "action_id": "a-rollback",
            "action": "increase_reinforcing_edge_strength",
            "updates": [],
            "rolled_back": False,
        }
    )
    bridge = CognitiveStateBridge(task_manager=_FakeRuntime())
    history = bridge.get_action_history(limit=5)
    assert history["resource"] == "self/action-history"
    assert history["items"][-1]["action_id"] == "a-rollback"

    rolled = bridge.rollback_self_action(action_id="a-rollback")
    assert rolled["resource"] == "self/rollback-action"
    assert rolled["rolled_back"] is True
