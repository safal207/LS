# ruff: noqa: E402
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from graph.runtime import GraphMemoryRuntime
from graph.models import RelationalEdge, ResonanceKnowledgeUnit


class _ExplodingResonanceStore:
    def store_resonance_unit(self, unit):  # pragma: no cover - helper
        raise RuntimeError("boom")


class _ExplodingRetrievalStore:
    def find_relevant_units(self, **kwargs):  # pragma: no cover - helper
        raise RuntimeError("boom")


def test_remember_success_stores_resonance_unit_when_signal_and_quality_pass(tmp_path):
    runtime = GraphMemoryRuntime(store_path=tmp_path / "cases.jsonl")
    item = {
        "text": "How do I speed up batching in this pipeline?",
        "clean_text": "speed up batching pipeline",
        "_intent": "optimization",
        "_why": "reduce latency",
        "_graph_mode": "full_run",
        "_resonance_score": 0.8,
        "_network_plan": {"route_key": "perf_route"},
    }

    saved = runtime.remember_success(
        item,
        answer_text="Use bounded queues and micro-batch sizing.",
        answer_quality={"overall": 0.85},
        contributors=[{"backend": "local", "model": "qwen"}],
    )

    assert saved is not None
    units = runtime.store.find_relevant_units(
        intent="optimization",
        query_text="batching pipeline",
        top_k=3,
    )
    assert len(units) == 1
    assert units[0].metadata.get("graph_mode") == "full_run"
    metrics = runtime.get_resonance_metrics()
    assert metrics["units_saved"] == 1
    assert metrics["units_save_skipped"] == 0
    assert metrics["units_save_errors"] == 0


def test_remember_success_skips_resonance_unit_in_reuse_mode(tmp_path):
    runtime = GraphMemoryRuntime(store_path=tmp_path / "cases.jsonl")
    item = {
        "text": "Repeat prior answer quickly",
        "clean_text": "repeat prior answer",
        "_intent": "reuse",
        "_graph_runtime": {"mode": "reuse"},
        "_resonance_score": 0.95,
        "_network_plan": {"route_key": "reuse_route"},
    }

    saved = runtime.remember_success(
        item,
        answer_text="Reusing previous answer.",
        answer_quality={"overall": 0.99},
    )

    assert saved is not None
    units = runtime.store.find_relevant_units(query_text="repeat prior answer", top_k=3)
    assert units == []
    metrics = runtime.get_resonance_metrics()
    assert metrics["units_saved"] == 0
    assert metrics["units_save_skipped"] == 1
    assert metrics["units_save_errors"] == 0


def test_inject_resonance_hints_returns_compact_hints_when_units_exist(tmp_path):
    runtime = GraphMemoryRuntime(store_path=tmp_path / "cases.jsonl")
    runtime.remember_success(
        {
            "text": "How do I speed up batching in this pipeline?",
            "clean_text": "speed up batching pipeline",
            "_intent": "optimization",
            "_why": "reduce latency",
            "_graph_mode": "full_run",
            "_resonance_score": 0.81,
            "_goal_alignment_score": 0.77,
            "_network_plan": {"route_key": "perf_route"},
        },
        answer_text="Use bounded queues\n\n and   micro-batch sizing to keep throughput stable.",
        answer_quality={"overall": 0.85},
    )

    item = {
        "text": "Need to speed up batching pipeline latency",
        "clean_text": "speed up batching pipeline",
        "_intent": "optimization",
        "_why": "reduce latency",
    }
    hints = runtime.inject_resonance_hints(item, top_k=3)

    assert hints
    assert item["_resonance_hints"] == hints
    assert hints[0]["intent"] == "optimization"
    assert hints[0]["route_key"] == "perf_route"
    assert isinstance(hints[0]["resonance_score"], float)
    assert "bounded queues" in (hints[0]["answer_pattern"] or "")
    assert "\n" not in (hints[0]["answer_pattern"] or "")
    metrics = runtime.get_resonance_metrics()
    assert metrics["hint_injection_calls"] == 1
    assert metrics["retrieval_hit"] == 1
    assert metrics["retrieval_miss"] == 0
    assert metrics["retrieval_empty_query"] == 0
    assert metrics["hint_count_total"] == len(hints)
    assert metrics["avg_hints_per_hit"] == float(len(hints))
    assert metrics["avg_hint_resonance_score"] > 0.0
    assert metrics["avg_hint_alignment_score"] > 0.0


def test_inject_resonance_hints_is_empty_when_no_relevant_units(tmp_path):
    runtime = GraphMemoryRuntime(store_path=tmp_path / "cases.jsonl")
    item = {
        "text": "Question with no known route",
        "clean_text": "unknown route query",
        "_intent": "unknown",
    }

    hints = runtime.inject_resonance_hints(item, top_k=3)

    assert hints == []
    assert item["_resonance_hints"] == []
    metrics = runtime.get_resonance_metrics()
    assert metrics["hint_injection_calls"] == 1
    assert metrics["retrieval_miss"] == 1
    assert metrics["retrieval_hit"] == 0
    assert metrics["hint_count_total"] == 0


def test_inject_resonance_hints_empty_query_updates_metrics_and_safe_averages(tmp_path):
    runtime = GraphMemoryRuntime(store_path=tmp_path / "cases.jsonl")
    item = {
        "text": "   ",
        "clean_text": "",
    }

    hints = runtime.inject_resonance_hints(item, top_k=3)

    assert hints == []
    assert item["_resonance_hints"] == []
    metrics = runtime.get_resonance_metrics()
    assert metrics["hint_injection_calls"] == 1
    assert metrics["retrieval_empty_query"] == 1
    assert metrics["retrieval_miss"] == 0
    assert metrics["retrieval_hit"] == 0
    assert metrics["avg_hints_per_hit"] == 0.0
    assert metrics["avg_hint_resonance_score"] == 0.0
    assert metrics["avg_hint_alignment_score"] == 0.0


def test_remember_success_store_resonance_exception_updates_error_counter(tmp_path):
    runtime = GraphMemoryRuntime(store_path=tmp_path / "cases.jsonl")
    runtime.store.store_resonance_unit = _ExplodingResonanceStore().store_resonance_unit
    item = {
        "text": "How do I speed up batching in this pipeline?",
        "clean_text": "speed up batching pipeline",
        "_intent": "optimization",
        "_why": "reduce latency",
        "_graph_mode": "full_run",
        "_resonance_score": 0.8,
        "_network_plan": {"route_key": "perf_route"},
    }

    saved = runtime.remember_success(
        item,
        answer_text="Use bounded queues and micro-batch sizing.",
        answer_quality={"overall": 0.85},
    )

    assert saved is not None
    metrics = runtime.get_resonance_metrics()
    assert metrics["units_saved"] == 0
    assert metrics["units_save_errors"] == 1


def test_inject_resonance_hints_exception_path_updates_error_counter(tmp_path):
    runtime = GraphMemoryRuntime(store_path=tmp_path / "cases.jsonl")
    runtime.store.find_relevant_units = _ExplodingRetrievalStore().find_relevant_units
    item = {
        "text": "Need known route",
        "clean_text": "need known route",
        "_intent": "optimization",
    }

    hints = runtime.inject_resonance_hints(item, top_k=3)

    assert hints == []
    assert item["_resonance_hints"] == []
    metrics = runtime.get_resonance_metrics()
    assert metrics["hint_injection_calls"] == 1
    assert metrics["hint_injection_errors"] == 1


def test_adapt_relational_edges_from_outcome_updates_recent_edges(tmp_path):
    runtime = GraphMemoryRuntime(store_path=tmp_path / "cases.jsonl")
    src = runtime.store.store_resonance_unit(
        ResonanceKnowledgeUnit(
            source_question="src",
            intent="learning",
            resonance_score=0.9,
            alignment_score=0.8,
        )
    )
    dst = runtime.store.store_resonance_unit(
        ResonanceKnowledgeUnit(
            source_question="dst",
            intent="learning",
            resonance_score=0.85,
            alignment_score=0.75,
        )
    )
    edge = RelationalEdge(
        target_unit_id=dst.unit_id,
        relation_type="reinforces",
        strength=0.4,
    )
    runtime.store.store_relational_edge(src.unit_id, edge)

    summary = runtime.adapt_relational_edges_from_outcome(
        feedback_polarity=0.7,
        resonance_score=0.8,
        review_decision="approved",
        incident_published=False,
        top_k=2,
    )

    assert summary["updated_edges"] >= 1
    updated_src = next(u for u in runtime.store.list_resonance_units() if u.unit_id == src.unit_id)
    updated_edge = next(r for r in updated_src.relations if r.get("edge_id") == edge.edge_id)
    assert float(updated_edge["strength"]) > 0.4


def test_adapt_relational_edges_from_outcome_handles_empty_graph(tmp_path):
    runtime = GraphMemoryRuntime(store_path=tmp_path / "cases.jsonl")
    summary = runtime.adapt_relational_edges_from_outcome(review_decision="approved")
    assert summary["updated_edges"] == 0
    assert summary["scanned_units"] == 0
