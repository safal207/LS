from __future__ import annotations

from graph.memory_store import MemoryGraphStore
from graph.models import RelationalFieldSnapshot, ResonanceKnowledgeUnit


def test_memory_store_persists_relational_snapshots_separately(tmp_path) -> None:
    store = MemoryGraphStore(tmp_path / "cases.jsonl")

    snapshot = RelationalFieldSnapshot(
        field_id="",
        timestamp="",
        participants=["alice", "bob"],
        interaction_scope="human-human",
        tension_score=0.82,
        alignment_score=0.24,
        dominant_signal="tension",
        background_pressure=["urgency", "overload"],
        foreground_expression=["pressure"],
        notes="mvp test",
        metadata={"source": "unit-test"},
    )

    stored = store.store_relational_snapshot(snapshot)

    assert stored.field_id
    assert stored.timestamp

    snapshots = store.list_relational_snapshots()
    assert len(snapshots) == 1
    assert snapshots[0].dominant_signal == "tension"

    relational_path = (tmp_path / "cases.jsonl").with_name(
        "relational_field_snapshots.jsonl"
    )
    assert relational_path.exists()


def test_memory_store_relational_does_not_mix_with_resonance_units(tmp_path) -> None:
    store = MemoryGraphStore(tmp_path / "cases.jsonl")

    store.store_relational_snapshot(
        RelationalFieldSnapshot(
            field_id="rf-1",
            timestamp="2026-01-01T00:00:00+00:00",
            participants=[],
            interaction_scope="human-human",
            tension_score=0.4,
            alignment_score=0.2,
            dominant_signal="tension",
            background_pressure=[],
            foreground_expression=[],
            notes="",
            metadata={},
        )
    )

    store.store_resonance_unit(
        ResonanceKnowledgeUnit(
            source_question="Почему вы выбрали этот подход?",
            resonance_score=0.71,
            alignment_score=0.69,
        )
    )

    assert len(store.list_relational_snapshots()) == 1
    assert len(store.list_resonance_units()) == 1
