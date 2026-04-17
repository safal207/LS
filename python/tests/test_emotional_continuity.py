from __future__ import annotations

from modules.graph.memory_store import MemoryGraphStore


def test_emotional_continuity_persists_and_restores(tmp_path) -> None:
    store_path = tmp_path / "graph_memory" / "cases.jsonl"
    store = MemoryGraphStore(store_path)
    store.update_emotional_memory_from_cycle(
        cycle_id="cy-1",
        source="care_cycle",
        resonance_score=0.8,
        alignment_score=0.8,
        coherence_score=0.75,
        user_feedback="thank you",
    )
    continuity = store.get_emotional_continuity_state()
    assert continuity["last_emotional_state"] in {"warm", "joyful"}
    assert continuity["bond_strength"] > 0.0
    assert 0.05 <= continuity["emotional_decay"] <= 1.0

    restored = MemoryGraphStore(store_path)
    relational_self = restored.get_relational_self()
    assert relational_self.last_emotional_state == continuity["last_emotional_state"]
    assert float(relational_self.bond_strength) == float(continuity["bond_strength"])
    assert 0.05 <= float(relational_self.emotional_decay) <= 1.0


def test_emotional_half_life_affects_decay(tmp_path) -> None:
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    store.store_emotional_memory_entry(
        {
            "timestamp": "2020-01-01T00:00:00+00:00",
            "emotional_tone": "warm",
            "bond_strength": 0.7,
            "confidence": 0.9,
            "emotional_half_life_hours": 12.0,
        }
    )
    rows = store.get_emotional_memory(limit=1)
    assert rows
    assert rows[0]["temporal_decay"] <= 0.06
