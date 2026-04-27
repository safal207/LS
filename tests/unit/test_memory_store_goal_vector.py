from pathlib import Path

from modules.graph.memory_store import MemoryGraphStore, _cosine_sim_dense
from modules.graph.models import ResonanceKnowledgeUnit


def test_cosine_sim_dense_orthogonal() -> None:
    assert _cosine_sim_dense([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_find_relevant_units_prefers_goal_vector_match(tmp_path: Path) -> None:
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    store.store_resonance_unit(
        ResonanceKnowledgeUnit(
            source_question="q1",
            intent="plan",
            why="a",
            goal_vector=[0.0, 1.0, 0.0],
            resonance_score=0.5,
        )
    )
    store.store_resonance_unit(
        ResonanceKnowledgeUnit(
            source_question="q2",
            intent="plan",
            why="a",
            goal_vector=[1.0, 0.0, 0.0],
            resonance_score=0.5,
        )
    )
    out = store.find_relevant_units(
        intent="plan",
        why="a",
        goal_vector=[0.9, 0.1, 0.0],
        top_k=2,
    )
    assert len(out) == 2
    assert "q2" in out[0].source_question
