from __future__ import annotations

from decimal import Decimal

from modules.cel import (
    CRDTReputationStore,
    ContributorImpact,
    CreationEvent,
    IncrementalAttributionEngine,
)


def _event(
    event_id: str,
    project_id: str,
    contributors: list[ContributorImpact],
    parents: list[str] | None = None,
) -> CreationEvent:
    return CreationEvent(
        event_id=event_id,
        project_id=project_id,
        event_type="code_committed",
        ts=1710000000,
        policy_version="v1.0",
        contributors=tuple(contributors),
        parents=tuple(parents or []),
        base_weight=1.0,
    )


def test_incremental_engine_idempotent_on_duplicate_event_id() -> None:
    engine = IncrementalAttributionEngine(lineage_decay=0.75)
    event = _event("evt_1", "proj_1", [ContributorImpact("agent_a", 1.0, 1.0)])

    assert engine.add_event(event) is True
    assert engine.add_event(event) is False

    scores = engine.project_actor_scores("proj_1")
    assert scores["agent_a"] == 1.0


def test_incremental_engine_applies_lineage_decay_from_parent() -> None:
    engine = IncrementalAttributionEngine(lineage_decay=0.5)
    parent = _event("evt_p", "proj_1", [ContributorImpact("agent_a", 1.0, 1.0)])
    child = _event("evt_c", "proj_1", [ContributorImpact("agent_b", 0.4, 1.0)], parents=["evt_p"])

    assert engine.add_event(parent)
    assert engine.add_event(child)

    scores = engine.project_actor_scores("proj_1")
    # parent contributes 1.0 to itself and 0.5 via child lineage
    assert scores["agent_a"] == 1.5
    assert scores["agent_b"] == 0.4


def test_payout_hash_deterministic_for_equal_inputs() -> None:
    e1 = _event("evt_1", "proj_1", [ContributorImpact("agent_a", 1.0, 1.0)])
    e2 = _event("evt_2", "proj_1", [ContributorImpact("agent_b", 2.0, 1.0)], parents=["evt_1"])

    first = IncrementalAttributionEngine(lineage_decay=0.75)
    second = IncrementalAttributionEngine(lineage_decay=0.75)

    assert first.add_event(e1)
    assert first.add_event(e2)
    assert second.add_event(e1)
    assert second.add_event(e2)

    snap_1 = first.build_payout_snapshot("proj_1", policy_version="v1.0", total_value=Decimal("100"))
    snap_2 = second.build_payout_snapshot("proj_1", policy_version="v1.0", total_value=Decimal("100"))

    assert snap_1.input_snapshot_hash == snap_2.input_snapshot_hash
    assert snap_1.output_payout_hash == snap_2.output_payout_hash


def test_crdt_reputation_store_merge_is_commutative() -> None:
    left = CRDTReputationStore()
    right = CRDTReputationStore()

    left.add_score("agent_a", score=1.0, replica_id="r1")
    right.add_score("agent_a", score=2.0, replica_id="r2")

    left_then_right = CRDTReputationStore()
    left_then_right.merge(left)
    left_then_right.merge(right)

    right_then_left = CRDTReputationStore()
    right_then_left.merge(right)
    right_then_left.merge(left)

    assert left_then_right.get_smoothed_score("agent_a") == right_then_left.get_smoothed_score("agent_a")
    assert left_then_right.get_smoothed_score("agent_a") > 0.5
