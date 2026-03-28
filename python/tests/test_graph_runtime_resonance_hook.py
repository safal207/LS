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
