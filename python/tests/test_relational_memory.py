# -*- coding: utf-8 -*-
"""Tests for relational memory: RelationalEdge, store_relational_edge,
get_relational_graph, get_resonance_with_relations, and suggest_edge_from_resonance."""
from __future__ import annotations

from pathlib import Path

import pytest

from modules.agent.relational_policy_engine import suggest_edge_from_resonance
from modules.graph.memory_store import MemoryGraphStore
from modules.graph.models import RelationalEdge, ResonanceKnowledgeUnit


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_store(tmp_path: Path) -> MemoryGraphStore:
    return MemoryGraphStore(tmp_path / "cases.jsonl")


def _unit(
    source_question: str = "Why does X happen?",
    resonance_score: float = 0.8,
    alignment_score: float = 0.6,
    intent: str | None = "understand",
    why: str | None = None,
) -> ResonanceKnowledgeUnit:
    return ResonanceKnowledgeUnit(
        source_question=source_question,
        resonance_score=resonance_score,
        alignment_score=alignment_score,
        intent=intent,
        why=why,
    )


# ─────────────────────────────────────────────────────────────
# RelationalEdge — model
# ─────────────────────────────────────────────────────────────

def test_relational_edge_defaults() -> None:
    edge = RelationalEdge(target_unit_id="abc", relation_type="reinforces")
    assert edge.target_unit_id == "abc"
    assert edge.relation_type == "reinforces"
    assert 0.0 <= edge.strength <= 1.0
    assert edge.edge_id
    assert edge.learned_at


def test_relational_edge_roundtrip() -> None:
    edge = RelationalEdge(
        target_unit_id="unit-99",
        relation_type="contradicts",
        strength=0.75,
        metadata={"source": "test"},
    )
    restored = RelationalEdge.from_dict(edge.to_dict())
    assert restored.target_unit_id == edge.target_unit_id
    assert restored.relation_type == edge.relation_type
    assert restored.strength == edge.strength
    assert restored.edge_id == edge.edge_id
    assert restored.metadata == {"source": "test"}


def test_relational_edge_invalid_type_falls_back_to_reinforces() -> None:
    edge = RelationalEdge.from_dict({"target_unit_id": "x", "relation_type": "unknown_type"})
    assert edge.relation_type == "reinforces"


def test_resonance_unit_has_relations_field() -> None:
    unit = _unit()
    assert hasattr(unit, "relations")
    assert isinstance(unit.relations, list)


def test_resonance_unit_relations_roundtrip() -> None:
    edge = RelationalEdge(target_unit_id="other-unit", relation_type="specializes")
    unit = _unit()
    unit.relations.append(edge.to_dict())

    restored = ResonanceKnowledgeUnit.from_dict(unit.to_dict())
    assert len(restored.relations) == 1
    assert restored.relations[0]["target_unit_id"] == "other-unit"
    assert restored.relations[0]["relation_type"] == "specializes"


# ─────────────────────────────────────────────────────────────
# store_relational_edge
# ─────────────────────────────────────────────────────────────

def test_store_relational_edge_appends_to_unit(tmp_store: MemoryGraphStore) -> None:
    unit = _unit()
    tmp_store.store_resonance_unit(unit)

    edge = RelationalEdge(target_unit_id="other", relation_type="reinforces", strength=0.9)
    updated = tmp_store.store_relational_edge(unit.unit_id, edge)

    assert updated is not None
    assert len(updated.relations) == 1
    assert updated.relations[0]["target_unit_id"] == "other"


def test_store_relational_edge_persists(tmp_store: MemoryGraphStore) -> None:
    unit = _unit()
    tmp_store.store_resonance_unit(unit)

    edge = RelationalEdge(target_unit_id="persisted", relation_type="generalizes")
    tmp_store.store_relational_edge(unit.unit_id, edge)

    reloaded = tmp_store.list_resonance_units()
    assert len(reloaded) == 1
    assert len(reloaded[0].relations) == 1
    assert reloaded[0].relations[0]["target_unit_id"] == "persisted"


def test_store_relational_edge_deduplicates(tmp_store: MemoryGraphStore) -> None:
    unit = _unit()
    tmp_store.store_resonance_unit(unit)

    edge = RelationalEdge(target_unit_id="dup-target", relation_type="reinforces")
    tmp_store.store_relational_edge(unit.unit_id, edge)
    tmp_store.store_relational_edge(unit.unit_id, edge)  # same edge_id → skip

    reloaded = tmp_store.list_resonance_units()
    assert len(reloaded[0].relations) == 1


def test_store_relational_edge_returns_none_for_missing_unit(tmp_store: MemoryGraphStore) -> None:
    edge = RelationalEdge(target_unit_id="x", relation_type="reinforces")
    result = tmp_store.store_relational_edge("nonexistent-id", edge)
    assert result is None


# ─────────────────────────────────────────────────────────────
# get_relational_graph
# ─────────────────────────────────────────────────────────────

def test_get_relational_graph_returns_root_node(tmp_store: MemoryGraphStore) -> None:
    unit = _unit()
    tmp_store.store_resonance_unit(unit)

    graph = tmp_store.get_relational_graph(unit.unit_id)

    assert graph["root_unit_id"] == unit.unit_id
    assert len(graph["nodes"]) == 1
    assert graph["nodes"][0]["unit_id"] == unit.unit_id


def test_get_relational_graph_traverses_edges(tmp_store: MemoryGraphStore) -> None:
    unit_a = _unit("question A")
    unit_b = _unit("question B")
    tmp_store.store_resonance_unit(unit_a)
    tmp_store.store_resonance_unit(unit_b)

    edge = RelationalEdge(
        target_unit_id=unit_b.unit_id,
        relation_type="reinforces",
        strength=0.8,
    )
    tmp_store.store_relational_edge(unit_a.unit_id, edge)

    graph = tmp_store.get_relational_graph(unit_a.unit_id, depth=1)

    node_ids = {n["unit_id"] for n in graph["nodes"]}
    assert unit_a.unit_id in node_ids
    assert unit_b.unit_id in node_ids
    assert len(graph["edges"]) == 1
    assert graph["edges"][0]["relation_type"] == "reinforces"


def test_get_relational_graph_missing_unit(tmp_store: MemoryGraphStore) -> None:
    graph = tmp_store.get_relational_graph("no-such-id")
    assert graph["nodes"] == []
    assert graph["edges"] == []


def test_get_relational_graph_respects_depth(tmp_store: MemoryGraphStore) -> None:
    # Chain: A → B → C
    unit_a = _unit("A")
    unit_b = _unit("B")
    unit_c = _unit("C")
    for u in (unit_a, unit_b, unit_c):
        tmp_store.store_resonance_unit(u)

    tmp_store.store_relational_edge(
        unit_a.unit_id,
        RelationalEdge(target_unit_id=unit_b.unit_id, relation_type="reinforces"),
    )
    tmp_store.store_relational_edge(
        unit_b.unit_id,
        RelationalEdge(target_unit_id=unit_c.unit_id, relation_type="specializes"),
    )

    graph_depth1 = tmp_store.get_relational_graph(unit_a.unit_id, depth=1)
    graph_depth2 = tmp_store.get_relational_graph(unit_a.unit_id, depth=2)

    node_ids_d1 = {n["unit_id"] for n in graph_depth1["nodes"]}
    node_ids_d2 = {n["unit_id"] for n in graph_depth2["nodes"]}

    assert unit_c.unit_id not in node_ids_d1
    assert unit_c.unit_id in node_ids_d2


# ─────────────────────────────────────────────────────────────
# get_resonance_with_relations
# ─────────────────────────────────────────────────────────────

def test_get_resonance_with_relations_structure(tmp_store: MemoryGraphStore) -> None:
    unit = _unit(resonance_score=0.9)
    tmp_store.store_resonance_unit(unit)

    edge = RelationalEdge(target_unit_id="other", relation_type="emotional_link")
    tmp_store.store_relational_edge(unit.unit_id, edge)

    items = tmp_store.get_resonance_with_relations(top_k=5, min_resonance_score=0.3)

    assert len(items) == 1
    assert "unit" in items[0]
    assert "relations" in items[0]
    assert items[0]["unit"]["unit_id"] == unit.unit_id
    assert len(items[0]["relations"]) == 1
    assert items[0]["relations"][0]["relation_type"] == "emotional_link"


def test_get_resonance_with_relations_empty_when_below_threshold(
    tmp_store: MemoryGraphStore,
) -> None:
    unit = _unit(resonance_score=0.1)
    tmp_store.store_resonance_unit(unit)

    items = tmp_store.get_resonance_with_relations(top_k=5, min_resonance_score=0.5)
    assert items == []


# ─────────────────────────────────────────────────────────────
# suggest_edge_from_resonance
# ─────────────────────────────────────────────────────────────

def test_suggest_edge_returns_none_when_scores_too_low() -> None:
    a = _unit(resonance_score=0.3)
    b = _unit(resonance_score=0.9)
    assert suggest_edge_from_resonance(a, b) is None


def test_suggest_edge_reinforces_when_same_intent() -> None:
    a = _unit(resonance_score=0.8, intent="understand")
    b = _unit(resonance_score=0.7, intent="understand")
    edge = suggest_edge_from_resonance(a, b)
    assert edge is not None
    assert edge.relation_type == "reinforces"
    assert edge.target_unit_id == b.unit_id


def test_suggest_edge_specializes_on_high_alignment_different_intents() -> None:
    a = _unit(resonance_score=0.75, alignment_score=0.7, intent="diagnose")
    b = _unit(resonance_score=0.65, alignment_score=0.6, intent="repair")
    edge = suggest_edge_from_resonance(a, b)
    assert edge is not None
    assert edge.relation_type == "specializes"


def test_suggest_edge_generalizes_when_score_gap_is_large() -> None:
    a = _unit(resonance_score=0.95, alignment_score=0.4, intent="high-res")
    b = _unit(resonance_score=0.65, alignment_score=0.4, intent="low-res")
    edge = suggest_edge_from_resonance(a, b)
    assert edge is not None
    assert edge.relation_type == "generalizes"


def test_suggest_edge_strength_is_min_of_scores() -> None:
    a = _unit(resonance_score=0.9, intent="same")
    b = _unit(resonance_score=0.7, intent="same")
    edge = suggest_edge_from_resonance(a, b)
    assert edge is not None
    assert edge.strength == pytest.approx(0.7, abs=1e-4)
