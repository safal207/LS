# ruff: noqa: E402
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from graph.memory_store import MemoryGraphStore
from graph.models import ResonanceKnowledgeUnit
from omni.qwen_omni_worker import QwenOmniWorker


def test_qwen_omni_worker_fallback_stores_unit(tmp_path, monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    worker = QwenOmniWorker(
        graph_store=store,
        audio_provider=lambda: "user says hello",
        min_store_resonance_score=0.0,
    )

    unit = worker.capture_and_analyze(trigger="test")

    assert unit is not None
    assert unit.metadata.get("source") == "qwen_omni_worker"
    saved = store.list_resonance_units()
    assert len(saved) == 1
    assert saved[0].resonance_score >= 0.0


def test_qwen_omni_worker_on_response_failure_is_best_effort(tmp_path, monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    store = MemoryGraphStore(tmp_path / "cases.jsonl")

    def _boom(_payload):
        raise RuntimeError("callback failed")

    worker = QwenOmniWorker(
        graph_store=store,
        audio_provider=lambda: "user says hello",
        on_response=_boom,
        min_store_resonance_score=0.0,
    )

    unit = worker.capture_and_analyze(trigger="test")

    assert unit is not None
    assert unit.metadata.get("source") == "qwen_omni_worker"
    saved = store.list_resonance_units()
    assert len(saved) == 1
    assert saved[0].resonance_score >= 0.0


def test_qwen_omni_worker_skips_low_signal_fallback_unit(tmp_path, monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    worker = QwenOmniWorker(
        graph_store=store,
        audio_provider=None,
        min_store_resonance_score=0.3,
    )

    monkeypatch.setattr(
        worker,
        "_capture_screen_frame",
        lambda: (None, {"capture": "unavailable", "reason": "test"}),
    )

    unit = worker.capture_and_analyze(trigger="test")

    assert unit is None
    assert store.list_resonance_units() == []


def test_qwen_omni_worker_store_failure_is_best_effort(tmp_path, monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    worker = QwenOmniWorker(
        graph_store=store,
        audio_provider=lambda: "user says hello",
        min_store_resonance_score=0.0,
    )

    def _boom(_unit):
        raise RuntimeError("boom")

    monkeypatch.setattr(store, "store_resonance_unit", _boom)
    unit = worker.capture_and_analyze(trigger="test")

    assert unit is None
    assert store.list_resonance_units() == []


def test_qwen_omni_worker_last_insight_returns_deep_copy(tmp_path, monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    worker = QwenOmniWorker(
        graph_store=store,
        audio_provider=lambda: "user says hello",
        min_store_resonance_score=0.0,
    )

    worker._last_insight = {
        "source_question": "monitor current screen",
        "metadata": {"provider": "fallback"},
        "goal_vector": [0.1, 0.2],
        "causal_path": [{"kind": "screen"}],
    }

    payload = worker.get_last_insight()
    assert payload is not None

    payload["metadata"]["provider"] = "tampered"
    payload["goal_vector"][0] = 9.9
    payload["causal_path"][0]["kind"] = "mutated"

    assert worker._last_insight["metadata"]["provider"] == "fallback"
    assert worker._last_insight["goal_vector"][0] == 0.1
    assert worker._last_insight["causal_path"][0]["kind"] == "screen"


def test_qwen_omni_worker_auto_creates_relational_edge_from_high_confidence_context(tmp_path, monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    prior = store.store_resonance_unit(
        ResonanceKnowledgeUnit(
            source_question="prior contextual memory",
            intent="situational_awareness",
            why="maintain_background_context",
            resonance_score=0.92,
            alignment_score=0.74,
        )
    )
    worker = QwenOmniWorker(
        graph_store=store,
        audio_provider=lambda: "screen mentions prior contextual memory",
        min_store_resonance_score=0.0,
    )
    monkeypatch.setattr(
        worker,
        "_analyze_with_fallback",
        lambda **_: {
            "text": "prior contextual memory on screen",
            "intent": "situational_awareness",
            "why": "maintain_background_context",
            "resonance_score": 0.9,
            "alignment_score": 0.72,
            "causal_path": [],
            "metadata": {"provider": "fallback"},
        },
    )

    unit = worker.capture_and_analyze(trigger="test")

    assert unit is not None
    saved = [u for u in store.list_resonance_units() if u.unit_id == unit.unit_id][0]
    assert any(
        rel.get("target_unit_id") == prior.unit_id and rel.get("metadata", {}).get("mode") == "auto_commit"
        for rel in saved.relations
    )


def test_qwen_omni_worker_marks_low_confidence_relations_for_review(tmp_path, monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    store.store_resonance_unit(
        ResonanceKnowledgeUnit(
            source_question="weak prior",
            intent="situational_awareness",
            why="maintain_background_context",
            resonance_score=0.61,
            alignment_score=0.3,
        )
    )
    worker = QwenOmniWorker(
        graph_store=store,
        audio_provider=lambda: "weak prior mention",
        min_store_resonance_score=0.0,
    )
    monkeypatch.setattr(
        worker,
        "_analyze_with_fallback",
        lambda **_: {
            "text": "weak prior mention now",
            "intent": "situational_awareness",
            "why": "maintain_background_context",
            "resonance_score": 0.62,
            "alignment_score": 0.2,
            "causal_path": [],
            "metadata": {"provider": "fallback"},
        },
    )

    unit = worker.capture_and_analyze(trigger="test")

    assert unit is not None
    saved = [u for u in store.list_resonance_units() if u.unit_id == unit.unit_id][0]
    candidates = list((saved.metadata or {}).get("relation_candidates") or [])
    assert len(candidates) >= 1
