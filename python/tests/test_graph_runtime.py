# -*- coding: utf-8 -*-
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
from graph.models import RelationalFieldSnapshot
from graph.retriever import MemoryGraphRetriever
from graph.runtime import GraphMemoryRuntime


def test_graph_runtime_returns_reuse_on_exact_match(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    store.remember(
        question_text="Почему вы выбрали этот стек?",
        clean_text="Почему вы выбрали этот стек?",
        answer_text="Потому что он дал баланс скорости и поддержки.",
    )
    runtime = GraphMemoryRuntime(store=store, retriever=MemoryGraphRetriever(store))

    decision = runtime.process(
        {
            "text": "Почему вы выбрали этот стек?",
            "clean_text": "Почему вы выбрали этот стек?",
        }
    )

    assert decision.mode == "reuse"
    assert decision.prior_answer == "Потому что он дал баланс скорости и поддержки."
    assert decision.matched_case_id


def test_graph_runtime_returns_refine_on_medium_similarity(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    store.remember(
        question_text="Why did you choose this stack for project delivery?",
        clean_text="Why did you choose this stack for project delivery?",
        answer_text="Because it balanced speed and maintainability.",
    )
    runtime = GraphMemoryRuntime(
        store=store,
        retriever=MemoryGraphRetriever(store),
        reuse_threshold=0.95,
        min_similarity=0.2,
    )

    decision = runtime.process(
        {
            "text": "Why did you choose this stack for the project?",
            "clean_text": "Why did you choose this stack for the project?",
        }
    )

    assert decision.mode == "refine"
    assert decision.prior_answer


def test_graph_runtime_returns_full_run_when_no_good_match(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    store.remember(
        question_text="Что такое Docker?",
        clean_text="Что такое Docker?",
        answer_text="Это контейнеризация.",
    )
    runtime = GraphMemoryRuntime(store=store, retriever=MemoryGraphRetriever(store))

    decision = runtime.process(
        {
            "text": "Почему вы выбрали этот стек?",
            "clean_text": "Почему вы выбрали этот стек?",
        }
    )

    assert decision.mode == "full_run"


def test_graph_runtime_remember_relational_snapshot_delegates_to_store(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    runtime = GraphMemoryRuntime(store=store, retriever=MemoryGraphRetriever(store))

    saved = runtime.remember_relational_snapshot(
        RelationalFieldSnapshot(
            field_id="",
            timestamp="",
            participants=["alice", "bob"],
            interaction_scope="human-human",
            tension_score=0.74,
            alignment_score=0.31,
            dominant_signal="tension",
            background_pressure=["urgency"],
            foreground_expression=["pressure"],
            notes="runtime facade test",
            metadata={},
        )
    )

    assert saved is not None
    assert store.list_relational_snapshots()
