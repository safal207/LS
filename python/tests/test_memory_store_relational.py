from __future__ import annotations

from graph.memory_store import MemoryGraphStore, build_relational_edge_update_preview
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


def test_build_relational_edge_update_preview_is_deterministic_and_bounded() -> None:
    first = build_relational_edge_update_preview(
        strength_before=0.61,
        review_decision="rejected",
        incident_published=True,
        receiver_resonance_score=0.22,
        relational_coherence=0.18,
    )
    second = build_relational_edge_update_preview(
        strength_before=0.61,
        review_decision="rejected",
        incident_published=True,
        receiver_resonance_score=0.22,
        relational_coherence=0.18,
    )

    assert first == second
    assert first["strength_before"] == 0.61
    assert 0.0 <= first["strength_after"] <= 1.0
    assert first["strength_after"] < first["strength_before"]
    assert first["reason_codes"] == [
        "rejected_review",
        "incident_published",
        "low_receiver_resonance",
        "low_relational_coherence",
    ]
    assert first["review_attention_required"] is True
    assert first["route_guidance"] == "validate_current_route"


def test_memory_store_preview_relational_edge_update_uses_shared_rule(tmp_path) -> None:
    store = MemoryGraphStore(tmp_path / "cases.jsonl")

    preview = store.preview_relational_edge_update(
        strength_before=0.33,
        review_decision="approved",
        incident_published=False,
        receiver_resonance_score=0.9,
        relational_coherence=0.82,
    )

    assert preview["strength_before"] == 0.33
    assert preview["strength_after"] > preview["strength_before"]
    assert preview["reason_codes"] == [
        "approved_review",
        "high_receiver_resonance",
    ]
    assert preview["review_attention_required"] is False
    assert preview["route_guidance"] == "continue_current_route"


def test_memory_store_relational_edge_updates_persist_and_lookup_latest(tmp_path) -> None:
    store = MemoryGraphStore(tmp_path / "cases.jsonl")

    store.store_relational_edge_update(
        {
            "cycle_id": "cid-1",
            "pattern_key": "tension",
            "selected_route": "r1",
            "strength_before": 0.4,
            "strength_after": 0.33,
            "reason_codes": ["rejected_review"],
        }
    )
    latest = store.store_relational_edge_update(
        {
            "cycle_id": "cid-2",
            "pattern_key": "tension",
            "selected_route": "r1",
            "strength_before": 0.33,
            "strength_after": 0.41,
            "reason_codes": ["approved_review"],
        }
    )

    updates = store.list_relational_edge_updates()
    assert len(updates) == 2
    assert latest["timestamp"]
    assert (
        store.get_latest_relational_edge_strength(
            pattern_key="tension",
            selected_route="r1",
        )
        == 0.41
    )


def test_memory_store_relational_edge_strength_lookup_is_scoped_by_pattern_and_route(
    tmp_path,
) -> None:
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    store.store_relational_edge_update(
        {
            "cycle_id": "cid-a",
            "pattern_key": "tension",
            "selected_route": "r1",
            "strength_after": 0.22,
        }
    )
    store.store_relational_edge_update(
        {
            "cycle_id": "cid-b",
            "pattern_key": "alignment",
            "selected_route": "r1",
            "strength_after": 0.77,
        }
    )

    assert (
        store.get_latest_relational_edge_strength(
            pattern_key="tension",
            selected_route="r1",
        )
        == 0.22
    )
    assert (
        store.get_latest_relational_edge_strength(
            pattern_key="alignment",
            selected_route="r1",
        )
        == 0.77
    )
