# ruff: noqa: E402
"""Tests for Resonance Evolve Lite.

Covers:
  - RouteEvolveConfig defaults
  - RouteSnapshot: from_dict / to_dict round-trip
  - _aggregate_path: common steps, overlap threshold, ordering
  - RouteEvolver.evolve: grouping, min_unit_count guard, versioning,
    confidence calc, path aggregation, no-regression on lower confidence
  - RouteEvolver.promote: threshold gating, rolled-back guard
  - RouteEvolver.rollback: flag setting, reason
  - MemoryGraphStore: store/list/get/list_promoted route snapshots
  - End-to-end: evolve → store → promote → rollback
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from graph.evolve import (
    RouteEvolveConfig,
    RouteEvolver,
    RouteSnapshot,
    _aggregate_path,
)
from graph.memory_store import MemoryGraphStore
from graph.models import ResonanceKnowledgeUnit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unit(
    intent: str = "solve",
    why: str | None = "explain",
    resonance: float = 0.8,
    path: list[dict] | None = None,
) -> ResonanceKnowledgeUnit:
    return ResonanceKnowledgeUnit(
        source_question="test",
        intent=intent,
        why=why,
        resonance_score=resonance,
        causal_path=path or [],
        metadata={"source": "care_cycle"},
    )


def _path(*strategies: str) -> list[dict]:
    return [{"step": i, "strategy": s, "outcome": "ok"} for i, s in enumerate(strategies)]


# ---------------------------------------------------------------------------
# RouteEvolveConfig
# ---------------------------------------------------------------------------


def test_config_defaults():
    cfg = RouteEvolveConfig()
    assert cfg.min_unit_count == 2
    assert cfg.promote_threshold == 0.7
    assert cfg.path_overlap_threshold == 0.5


# ---------------------------------------------------------------------------
# RouteSnapshot serialisation
# ---------------------------------------------------------------------------


def test_snapshot_round_trip():
    snap = RouteSnapshot(
        snapshot_id="abc",
        version=3,
        intent="solve",
        why="explain",
        aggregated_path=[{"strategy": "compare_options"}],
        confidence=0.85,
        source_unit_count=4,
        source_unit_ids=["u1", "u2"],
    )
    restored = RouteSnapshot.from_dict(snap.to_dict())
    assert restored.snapshot_id == "abc"
    assert restored.version == 3
    assert restored.confidence == 0.85
    assert restored.intent == "solve"
    assert not restored.promoted
    assert not restored.rolled_back


# ---------------------------------------------------------------------------
# _aggregate_path
# ---------------------------------------------------------------------------


def test_aggregate_path_all_shared():
    units = [
        _unit(path=_path("A", "B", "C")),
        _unit(path=_path("A", "B", "C")),
    ]
    result = _aggregate_path(units, overlap_threshold=0.5)
    strategies = [s["strategy"] for s in result]
    assert strategies == ["A", "B", "C"]


def test_aggregate_path_partial_overlap():
    units = [
        _unit(path=_path("A", "B", "X")),
        _unit(path=_path("A", "B", "Y")),
    ]
    result = _aggregate_path(units, overlap_threshold=0.5)
    strategies = [s["strategy"] for s in result]
    assert "A" in strategies
    assert "B" in strategies
    assert "X" not in strategies
    assert "Y" not in strategies


def test_aggregate_path_no_overlap():
    units = [
        _unit(path=_path("X")),
        _unit(path=_path("Y")),
    ]
    # threshold=0.9 requires steps to appear in >90% of units (both);
    # X and Y each appear in only 1 of 2 so neither qualifies.
    result = _aggregate_path(units, overlap_threshold=0.9)
    assert result == []


def test_aggregate_path_empty_units():
    assert _aggregate_path([], overlap_threshold=0.5) == []


def test_aggregate_path_order_from_first_unit():
    """Steps should appear in the order they were first seen in units[0]."""
    units = [
        _unit(path=_path("C", "A", "B")),
        _unit(path=_path("A", "B", "C")),
    ]
    result = _aggregate_path(units, overlap_threshold=0.5)
    strategies = [s["strategy"] for s in result]
    assert strategies.index("C") < strategies.index("A")


# ---------------------------------------------------------------------------
# RouteEvolver.evolve
# ---------------------------------------------------------------------------


def test_evolve_creates_snapshot_for_sufficient_group():
    evolver = RouteEvolver(RouteEvolveConfig(min_unit_count=2))
    units = [_unit(intent="solve", resonance=0.8), _unit(intent="solve", resonance=0.9)]
    snapshots = evolver.evolve(units)
    assert len(snapshots) == 1
    snap = snapshots[0]
    assert snap.intent == "solve"
    assert snap.version == 1
    assert snap.source_unit_count == 2
    assert abs(snap.confidence - 0.85) < 1e-4


def test_evolve_skips_group_below_min_unit_count():
    evolver = RouteEvolver(RouteEvolveConfig(min_unit_count=3))
    units = [_unit(intent="solve", resonance=0.8), _unit(intent="solve", resonance=0.9)]
    snapshots = evolver.evolve(units)
    assert len(snapshots) == 0


def test_evolve_separates_intents():
    evolver = RouteEvolver(RouteEvolveConfig(min_unit_count=2))
    units = [
        _unit(intent="solve", resonance=0.8),
        _unit(intent="solve", resonance=0.9),
        _unit(intent="explain", resonance=0.75),
        _unit(intent="explain", resonance=0.85),
    ]
    snapshots = evolver.evolve(units)
    assert len(snapshots) == 2
    intents = {s.intent for s in snapshots}
    assert intents == {"solve", "explain"}


def test_evolve_versions_existing_snapshot_on_higher_confidence():
    evolver = RouteEvolver(RouteEvolveConfig(min_unit_count=2))
    first = evolver.evolve([
        _unit(intent="solve", resonance=0.7),
        _unit(intent="solve", resonance=0.7),
    ])
    assert first[0].version == 1
    assert abs(first[0].confidence - 0.7) < 1e-4

    # Better group — should bump version
    second = evolver.evolve(
        [_unit(intent="solve", resonance=0.9), _unit(intent="solve", resonance=0.9)],
        existing_snapshots=first,
    )
    updated = next(s for s in second if s.intent == "solve")
    assert updated.version == 2
    assert updated.confidence > 0.7


def test_evolve_does_not_downgrade_existing_snapshot():
    evolver = RouteEvolver(RouteEvolveConfig(min_unit_count=2))
    first = evolver.evolve([
        _unit(intent="solve", resonance=0.9),
        _unit(intent="solve", resonance=0.9),
    ])
    # Weaker group — should NOT produce a new version
    second = evolver.evolve(
        [_unit(intent="solve", resonance=0.5), _unit(intent="solve", resonance=0.5)],
        existing_snapshots=first,
    )
    existing = next(s for s in second if s.intent == "solve")
    assert existing.version == 1
    assert existing.confidence >= 0.89


def test_evolve_aggregates_causal_paths():
    # threshold=0.9 requires both units to agree (2 > 0.9*2=1.8 → True).
    evolver = RouteEvolver(RouteEvolveConfig(min_unit_count=2, path_overlap_threshold=0.9))
    units = [
        _unit(intent="solve", path=_path("A", "B")),
        _unit(intent="solve", path=_path("A", "B")),
    ]
    snapshots = evolver.evolve(units)
    strategies = [s["strategy"] for s in snapshots[0].aggregated_path]
    assert "A" in strategies and "B" in strategies


def test_evolve_dominant_why():
    evolver = RouteEvolver(RouteEvolveConfig(min_unit_count=2))
    units = [
        _unit(intent="solve", why="explain", resonance=0.8),
        _unit(intent="solve", why="explain", resonance=0.8),
        _unit(intent="solve", why="debug", resonance=0.8),
    ]
    snapshots = evolver.evolve(units)
    assert snapshots[0].why == "explain"


def test_evolve_none_intent_maps_to_unknown():
    evolver = RouteEvolver(RouteEvolveConfig(min_unit_count=2))
    units = [_unit(intent=None, resonance=0.8), _unit(intent=None, resonance=0.8)]
    snapshots = evolver.evolve(units)
    assert snapshots[0].intent == "unknown"


# ---------------------------------------------------------------------------
# RouteEvolver.promote
# ---------------------------------------------------------------------------


def test_promote_above_threshold():
    evolver = RouteEvolver(RouteEvolveConfig(promote_threshold=0.7))
    snap = RouteSnapshot(
        snapshot_id="s1", version=1, intent="solve", why=None,
        aggregated_path=[], confidence=0.85,
        source_unit_count=3, source_unit_ids=[],
    )
    promoted = evolver.promote(snap)
    assert promoted.promoted
    assert promoted.promoted_at is not None


def test_promote_below_threshold_refused():
    evolver = RouteEvolver(RouteEvolveConfig(promote_threshold=0.7))
    snap = RouteSnapshot(
        snapshot_id="s1", version=1, intent="solve", why=None,
        aggregated_path=[], confidence=0.5,
        source_unit_count=3, source_unit_ids=[],
    )
    result = evolver.promote(snap)
    assert not result.promoted


def test_promote_rolled_back_snapshot_refused():
    evolver = RouteEvolver(RouteEvolveConfig(promote_threshold=0.5))
    snap = RouteSnapshot(
        snapshot_id="s1", version=1, intent="solve", why=None,
        aggregated_path=[], confidence=0.9,
        source_unit_count=3, source_unit_ids=[],
        rolled_back=True,
    )
    result = evolver.promote(snap)
    assert not result.promoted


# ---------------------------------------------------------------------------
# RouteEvolver.rollback
# ---------------------------------------------------------------------------


def test_rollback_clears_promoted():
    evolver = RouteEvolver()
    snap = RouteSnapshot(
        snapshot_id="s1", version=2, intent="solve", why=None,
        aggregated_path=[], confidence=0.9,
        source_unit_count=3, source_unit_ids=[],
        promoted=True,
    )
    rolled = evolver.rollback(snap, reason="caused regression")
    assert not rolled.promoted
    assert rolled.rolled_back
    assert rolled.rollback_reason == "caused regression"


def test_rollback_preserves_version_and_path():
    evolver = RouteEvolver()
    path = [{"strategy": "A"}]
    snap = RouteSnapshot(
        snapshot_id="s1", version=3, intent="debug", why="find bug",
        aggregated_path=path, confidence=0.8,
        source_unit_count=2, source_unit_ids=["u1"],
        promoted=True,
    )
    rolled = evolver.rollback(snap, reason="x")
    assert rolled.version == 3
    assert rolled.aggregated_path == path


# ---------------------------------------------------------------------------
# MemoryGraphStore — route snapshot persistence
# ---------------------------------------------------------------------------


def test_store_route_snapshot_and_list(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    snap = RouteSnapshot(
        snapshot_id="s1", version=1, intent="solve", why=None,
        aggregated_path=[], confidence=0.8,
        source_unit_count=2, source_unit_ids=[],
    )
    store.store_route_snapshot(snap)
    all_snaps = store.list_route_snapshots()
    assert len(all_snaps) == 1
    assert all_snaps[0].snapshot_id == "s1"


def test_store_route_snapshot_upserts(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    snap1 = RouteSnapshot(
        snapshot_id="s1", version=1, intent="solve", why=None,
        aggregated_path=[], confidence=0.7,
        source_unit_count=2, source_unit_ids=[],
    )
    snap2 = RouteSnapshot(
        snapshot_id="s1", version=2, intent="solve", why=None,
        aggregated_path=[], confidence=0.85,
        source_unit_count=3, source_unit_ids=[],
    )
    store.store_route_snapshot(snap1)
    store.store_route_snapshot(snap2)
    all_snaps = store.list_route_snapshots()
    assert len(all_snaps) == 1
    assert all_snaps[0].version == 2


def test_store_list_promoted(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    promoted = RouteSnapshot(
        snapshot_id="s1", version=1, intent="solve", why=None,
        aggregated_path=[], confidence=0.9,
        source_unit_count=2, source_unit_ids=[], promoted=True,
    )
    unpromoted = RouteSnapshot(
        snapshot_id="s2", version=1, intent="explain", why=None,
        aggregated_path=[], confidence=0.5,
        source_unit_count=2, source_unit_ids=[],
    )
    rolled_back = RouteSnapshot(
        snapshot_id="s3", version=1, intent="debug", why=None,
        aggregated_path=[], confidence=0.9,
        source_unit_count=2, source_unit_ids=[], promoted=True, rolled_back=True,
    )
    for s in [promoted, unpromoted, rolled_back]:
        store.store_route_snapshot(s)

    live = store.list_promoted_snapshots()
    assert len(live) == 1
    assert live[0].snapshot_id == "s1"


def test_store_get_route_snapshot(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    snap = RouteSnapshot(
        snapshot_id="my-snap", version=1, intent="x", why=None,
        aggregated_path=[], confidence=0.6,
        source_unit_count=2, source_unit_ids=[],
    )
    store.store_route_snapshot(snap)
    found = store.get_route_snapshot("my-snap")
    assert found is not None
    assert found.intent == "x"

    assert store.get_route_snapshot("no-such-id") is None


# ---------------------------------------------------------------------------
# End-to-end: evolve → store → promote → rollback
# ---------------------------------------------------------------------------


def test_e2e_evolve_store_promote_rollback(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    evolver = RouteEvolver(RouteEvolveConfig(min_unit_count=2, promote_threshold=0.7))

    units = [
        _unit(intent="solve", resonance=0.85, path=_path("A", "B")),
        _unit(intent="solve", resonance=0.90, path=_path("A", "B", "C")),
    ]

    # Evolve and store
    snapshots = evolver.evolve(units, existing_snapshots=store.list_route_snapshots())
    for s in snapshots:
        store.store_route_snapshot(s)

    snap = store.get_route_snapshot(snapshots[0].snapshot_id)
    assert snap is not None
    assert snap.version == 1
    assert not snap.promoted

    # Promote
    promoted = evolver.promote(snap)
    store.store_route_snapshot(promoted)
    assert len(store.list_promoted_snapshots()) == 1

    # Rollback
    rolled = evolver.rollback(promoted, reason="side-effect detected")
    store.store_route_snapshot(rolled)
    assert len(store.list_promoted_snapshots()) == 0
    assert store.get_route_snapshot(rolled.snapshot_id).rolled_back
