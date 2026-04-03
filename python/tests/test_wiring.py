# ruff: noqa: E402
"""Integration tests for the layer-wiring PR 364.

Wire 1 — find_relevant_units() uses decay-filtered units:
  - expired units never appear in results
  - fresh units rank above stale units with equal match score
  - decay_config parameter forwarded correctly

Wire 2 — CareCycleRunner triggers RouteEvolver after storing a resonance unit:
  - route snapshot created after first qualifying review
  - second review with same intent bumps version if confidence is higher
  - auto-promote fires when confidence >= threshold
  - evolver is best-effort (explosion does not break review)

Wire 3 — TensionAnalyzer stores RelationalFieldSnapshot to graph_store:
  - snapshot stored when graph_store passed to observe()
  - snapshot stored when graph_store set in __init__
  - store failure is best-effort (does not raise)
  - observation still returned even when store explodes
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from graph.care_cycle import CareCycleRunner
from graph.decay import ResonanceDecayConfig
from graph.derived_module_registry import DerivedModuleRegistry
from graph.evolve import RouteEvolveConfig, RouteEvolver
from graph.memory_store import MemoryGraphStore
from graph.models import ResonanceKnowledgeUnit
from graph.tension import TensionAnalyzer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _store(tmp_path: Path) -> MemoryGraphStore:
    return MemoryGraphStore(tmp_path / "cases.jsonl")


def _registry(tmp_path: Path) -> DerivedModuleRegistry:
    return DerivedModuleRegistry(tmp_path / "derived.json")


def _ts(hours_ago: float = 0.0) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


def _unit(
    source_question: str = "test",
    intent: str = "solve",
    resonance: float = 0.8,
    hours_ago: float = 0.0,
    source: str = "care_cycle",
) -> ResonanceKnowledgeUnit:
    return ResonanceKnowledgeUnit(
        source_question=source_question,
        intent=intent,
        resonance_score=resonance,
        timestamp=_ts(hours_ago),
        metadata={"source": source},
    )


def _add_module(registry: DerivedModuleRegistry, quality: float = 0.9) -> str:
    import uuid
    m = registry.create_or_update_from_success(
        parent_coalition_id="c1",
        source_route_key="route>local",
        domain=f"d-{uuid.uuid4().hex[:6]}",
        task_type="generic",
        preferred_backend="local",
        policy_type="prompt_policy",
        policy_text="ok",
        quality_score=quality,
    )
    return m.module_id


# ===========================================================================
# Wire 1 — find_relevant_units() respects decay
# ===========================================================================


def test_find_relevant_excludes_expired_units(tmp_path):
    store = _store(tmp_path)
    cfg = ResonanceDecayConfig(floor_score=0.05)
    half_life = cfg.half_life_for("care_cycle")

    fresh = _unit(source_question="how to solve x", intent="solve", hours_ago=0.0)
    expired = _unit(source_question="how to solve x", intent="solve",
                    hours_ago=15 * half_life)
    store.store_resonance_unit(fresh)
    store.store_resonance_unit(expired)

    results = store.find_relevant_units(intent="solve", decay_config=cfg)
    ids = {u.unit_id for u in results}
    assert fresh.unit_id in ids
    assert expired.unit_id not in ids


def test_find_relevant_ranks_fresh_above_stale(tmp_path):
    store = _store(tmp_path)
    cfg = ResonanceDecayConfig(floor_score=0.01)
    half_life = cfg.half_life_for("care_cycle")

    # Same resonance_score and same intent — only age differs.
    fresh = _unit(intent="explain", resonance=0.8, hours_ago=0.0)
    stale = _unit(intent="explain", resonance=0.8, hours_ago=half_life * 2)
    store.store_resonance_unit(stale)   # insert stale first
    store.store_resonance_unit(fresh)

    results = store.find_relevant_units(intent="explain", top_k=2, decay_config=cfg)
    assert len(results) == 2
    assert results[0].unit_id == fresh.unit_id


def test_find_relevant_no_decay_config_uses_defaults(tmp_path):
    store = _store(tmp_path)
    u = _unit(intent="debug", hours_ago=0.0)
    store.store_resonance_unit(u)

    results = store.find_relevant_units(intent="debug")
    assert len(results) == 1
    assert results[0].unit_id == u.unit_id


def test_find_relevant_empty_store(tmp_path):
    store = _store(tmp_path)
    assert store.find_relevant_units(intent="anything") == []


# ===========================================================================
# Wire 2 — CareCycleRunner triggers RouteEvolver
# ===========================================================================


def test_care_cycle_creates_route_snapshot_after_review(tmp_path):
    store = _store(tmp_path)
    registry = _registry(tmp_path)
    evolver = RouteEvolver(RouteEvolveConfig(min_unit_count=1, promote_threshold=0.99))
    runner = CareCycleRunner(
        registry, store,
        min_quality=0.7, min_trust=0.6, retire_trust=0.3,
        route_evolver=evolver,
    )
    mid = _add_module(registry, quality=0.9)

    runner.review(
        mid,
        cycle_id="c1",
        source_question="how to approach this problem",
        intent="solve",
        resonance_score=0.9,
        causal_path=[{"step": 0, "strategy": "decompose", "outcome": "ok"}],
    )

    snapshots = store.list_route_snapshots()
    assert len(snapshots) == 1
    assert snapshots[0].intent == "solve"


def test_care_cycle_bumps_snapshot_version_on_higher_confidence(tmp_path):
    store = _store(tmp_path)
    registry = _registry(tmp_path)
    evolver = RouteEvolver(RouteEvolveConfig(min_unit_count=1, promote_threshold=0.99))
    runner = CareCycleRunner(
        registry, store,
        min_quality=0.7, min_trust=0.6, retire_trust=0.3,
        route_evolver=evolver,
    )
    mid = _add_module(registry, quality=0.9)

    # First review — lower resonance
    runner.review(mid, source_question="q1", intent="explain", resonance_score=0.7,
                  causal_path=[{"step": 0, "strategy": "outline", "outcome": "ok"}])

    # Second review — higher resonance → should bump version
    runner.review(mid, source_question="q2", intent="explain", resonance_score=0.95,
                  causal_path=[{"step": 0, "strategy": "outline", "outcome": "ok"}])

    snap = store.list_route_snapshots()[0]
    assert snap.version == 2


def test_care_cycle_auto_promotes_snapshot_above_threshold(tmp_path):
    store = _store(tmp_path)
    registry = _registry(tmp_path)
    evolver = RouteEvolver(RouteEvolveConfig(min_unit_count=1, promote_threshold=0.7))
    runner = CareCycleRunner(
        registry, store,
        min_quality=0.7, min_trust=0.6, retire_trust=0.3,
        route_evolver=evolver,
    )
    mid = _add_module(registry, quality=0.9)

    runner.review(mid, source_question="q", intent="solve", resonance_score=0.85,
                  causal_path=[{"step": 0, "strategy": "A", "outcome": "ok"}])

    promoted = store.list_promoted_snapshots()
    assert len(promoted) == 1


def test_care_cycle_route_evolver_failure_is_best_effort(tmp_path):
    """An exploding RouteEvolver must not break the care cycle review."""
    store = _store(tmp_path)
    registry = _registry(tmp_path)

    class _BoomEvolver:
        def evolve(self, *a, **kw):
            raise RuntimeError("boom")

    runner = CareCycleRunner(
        registry, store,
        min_quality=0.7, min_trust=0.6, retire_trust=0.3,
        route_evolver=_BoomEvolver(),
    )
    mid = _add_module(registry, quality=0.9)
    result = runner.review(mid, source_question="q", intent="solve", resonance_score=0.9)

    assert result is not None
    assert result.state == "active"


def test_care_cycle_no_evolver_does_not_create_snapshots(tmp_path):
    store = _store(tmp_path)
    registry = _registry(tmp_path)
    runner = CareCycleRunner(registry, store, min_quality=0.7, min_trust=0.6)
    mid = _add_module(registry, quality=0.9)

    runner.review(mid, source_question="q", intent="solve", resonance_score=0.9)

    assert store.list_route_snapshots() == []


# ===========================================================================
# Wire 3 — TensionAnalyzer stores RelationalFieldSnapshot
# ===========================================================================


def test_tension_stores_snapshot_via_observe_kwarg(tmp_path):
    store = _store(tmp_path)
    analyzer = TensionAnalyzer()

    analyzer.observe(
        text="ты виноват в этом, всегда так делаешь!",
        graph_store=store,
    )

    assert len(store.list_relational_snapshots()) == 1


def test_tension_stores_snapshot_via_init_store(tmp_path):
    store = _store(tmp_path)
    analyzer = TensionAnalyzer(graph_store=store)

    analyzer.observe(text="помоги мне пожалуйста, прошу")

    assert len(store.list_relational_snapshots()) == 1


def test_tension_observe_kwarg_overrides_init_store(tmp_path):
    store_init = _store(tmp_path / "init")
    store_call = _store(tmp_path / "call")
    analyzer = TensionAnalyzer(graph_store=store_init)

    analyzer.observe(text="давай вместе", graph_store=store_call)

    # snapshot must go to the call-site store, not the init store
    assert len(store_call.list_relational_snapshots()) == 1
    assert len(store_init.list_relational_snapshots()) == 0


def test_tension_store_failure_is_best_effort(tmp_path):
    class _BoomStore:
        def store_relational_snapshot(self, _snap):
            raise RuntimeError("boom")

    analyzer = TensionAnalyzer()
    obs = analyzer.observe(
        text="это твоя вина! ты виноват!",
        graph_store=_BoomStore(),
    )
    assert obs is not None
    assert obs.tension_score >= 0.0


def test_tension_no_store_does_not_persist(tmp_path):
    store = _store(tmp_path)
    analyzer = TensionAnalyzer()  # no store wired

    analyzer.observe(text="neutral message")

    assert store.list_relational_snapshots() == []


def test_tension_snapshot_id_matches_observation_source_id(tmp_path):
    store = _store(tmp_path)
    analyzer = TensionAnalyzer()

    obs = analyzer.observe(text="I'm overwhelmed, too much", graph_store=store)
    snaps = store.list_relational_snapshots()
    assert len(snaps) == 1
    assert obs.source_snapshot_id == snaps[0].field_id
