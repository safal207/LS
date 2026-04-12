from __future__ import annotations

from modules.graph.memory_store import MemoryGraphStore
from modules.graph.models import RelationalEdge, ResonanceKnowledgeUnit


def test_update_relational_self_from_cycle_creates_snapshot(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    a = store.store_resonance_unit(
        ResonanceKnowledgeUnit(
            source_question="How do I focus?",
            intent="focus",
            resonance_score=0.82,
            alignment_score=0.77,
        )
    )
    b = store.store_resonance_unit(
        ResonanceKnowledgeUnit(
            source_question="How to rest better?",
            intent="recovery",
            resonance_score=0.74,
            alignment_score=0.71,
        )
    )
    store.store_relational_edge(
        a.unit_id,
        RelationalEdge(
            target_unit_id=b.unit_id,
            relation_type="reinforces",
            strength=0.8,
        ),
    )

    snapshot = store.update_self_from_cycle(cycle_id="care-1")

    assert snapshot.self_coherence_score > 0.0
    assert snapshot.schema_version == "1.0"
    assert len(snapshot.core_nodes) >= 2
    assert len(snapshot.self_identity_vector) == 4

    current = store.get_relational_self()
    assert current.snapshot_id == snapshot.snapshot_id

    history = store.get_coherence_history(limit=10)
    assert history
    assert history[-1]["cycle_id"] == "care-1"


def test_update_relational_self_applies_omni_fatigue_hook(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    store.store_resonance_unit(
        ResonanceKnowledgeUnit(
            source_question="Need gentler cadence",
            intent="support",
            resonance_score=0.7,
            alignment_score=0.75,
        )
    )

    snapshot = store.update_self_from_cycle(
        cycle_id="care-2",
        omni_insight={"signal": "fatigue"},
    )

    assert any(edge["relation_type"] == "emotional_link" for edge in snapshot.core_edges)
