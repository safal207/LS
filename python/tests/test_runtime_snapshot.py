# ruff: noqa: E402
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from graph.derived_module_registry import DerivedModuleRegistry
from graph.memory_store import MemoryGraphStore
from graph.models import RelationalFieldSnapshot, ResonanceKnowledgeUnit
from graph.runtime_snapshot import (
    CareCycleStatus,
    GraphMemoryStatus,
    OmniWorkerStatus,
    RuntimeStatusSnapshot,
    collect_runtime_status,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_store(tmp_path: Path) -> MemoryGraphStore:
    return MemoryGraphStore(tmp_path / "cases.jsonl")


def _make_registry(tmp_path: Path) -> DerivedModuleRegistry:
    return DerivedModuleRegistry(tmp_path / "derived.json")


def _add_module(registry: DerivedModuleRegistry, *, quality: float = 0.85, state: str = "active"):
    import uuid

    # Use a unique domain per call so each module gets a distinct module_id.
    domain = f"domain-{uuid.uuid4().hex[:8]}"
    m = registry.create_or_update_from_success(
        parent_coalition_id=f"c-{uuid.uuid4().hex[:6]}",
        source_route_key="route>local",
        domain=domain,
        task_type="generic",
        preferred_backend="local",
        policy_type="prompt_policy",
        policy_text="ok",
        quality_score=quality,
    )
    if state != "active":
        m.state = state
        registry.save_module(m)
    return m


# ---------------------------------------------------------------------------
# GraphMemoryStatus
# ---------------------------------------------------------------------------


def test_graph_memory_empty_store(tmp_path):
    store = _make_store(tmp_path)
    registry = _make_registry(tmp_path)
    snap = collect_runtime_status(graph_store=store, registry=registry)

    gm = snap.graph_memory
    assert isinstance(gm, GraphMemoryStatus)
    assert gm.total_cases == 0
    assert gm.total_resonance_units == 0
    assert gm.total_relational_snapshots == 0
    assert gm.avg_resonance_score == 0.0
    assert gm.avg_alignment_score == 0.0


def test_graph_memory_counts_cases_and_units(tmp_path):
    store = _make_store(tmp_path)
    registry = _make_registry(tmp_path)

    store.remember(
        question_text="q1",
        clean_text="q1",
        answer_text="a1",
    )
    store.remember(
        question_text="q2",
        clean_text="q2",
        answer_text="a2",
    )
    store.store_resonance_unit(
        ResonanceKnowledgeUnit(
            source_question="route A",
            resonance_score=0.8,
            alignment_score=0.6,
        )
    )
    store.store_resonance_unit(
        ResonanceKnowledgeUnit(
            source_question="route B",
            resonance_score=0.4,
            alignment_score=0.2,
        )
    )

    snap = collect_runtime_status(graph_store=store, registry=registry)
    gm = snap.graph_memory

    assert gm.total_cases == 2
    assert gm.total_resonance_units == 2
    assert gm.avg_resonance_score == round((0.8 + 0.4) / 2, 4)
    assert gm.avg_alignment_score == round((0.6 + 0.2) / 2, 4)


def test_graph_memory_counts_relational_snapshots(tmp_path):
    store = _make_store(tmp_path)
    registry = _make_registry(tmp_path)

    store.store_relational_snapshot(
        RelationalFieldSnapshot(
            field_id="",
            timestamp="",
            tension_score=0.5,
            alignment_score=0.7,
        )
    )

    snap = collect_runtime_status(graph_store=store, registry=registry)
    assert snap.graph_memory.total_relational_snapshots == 1


# ---------------------------------------------------------------------------
# CareCycleStatus
# ---------------------------------------------------------------------------


def test_care_cycle_empty_registry(tmp_path):
    store = _make_store(tmp_path)
    registry = _make_registry(tmp_path)
    snap = collect_runtime_status(graph_store=store, registry=registry)

    cc = snap.care_cycle
    assert isinstance(cc, CareCycleStatus)
    assert cc.total_modules == 0
    assert cc.active == 0
    assert cc.review == 0
    assert cc.retired == 0
    assert cc.avg_trust_score == 0.0
    assert cc.avg_quality_score == 0.0
    assert cc.total_care_cycles == 0


def test_care_cycle_counts_module_states(tmp_path):
    store = _make_store(tmp_path)
    registry = _make_registry(tmp_path)

    _add_module(registry, quality=0.9, state="active")
    _add_module(registry, quality=0.5, state="review")
    _add_module(registry, quality=0.3, state="retired")

    snap = collect_runtime_status(graph_store=store, registry=registry)
    cc = snap.care_cycle

    assert cc.total_modules == 3
    assert cc.active == 1
    assert cc.review == 1
    assert cc.retired == 1


def test_care_cycle_avg_scores(tmp_path):
    store = _make_store(tmp_path)
    registry = _make_registry(tmp_path)

    _add_module(registry, quality=0.8)
    _add_module(registry, quality=0.6)

    snap = collect_runtime_status(graph_store=store, registry=registry)
    cc = snap.care_cycle

    assert cc.total_modules == 2
    assert 0.0 < cc.avg_quality_score <= 1.0
    assert 0.0 < cc.avg_trust_score <= 1.0


def test_care_cycle_total_care_cycles(tmp_path):
    store = _make_store(tmp_path)
    registry = _make_registry(tmp_path)

    m = _add_module(registry, quality=0.85)
    m.care_cycles = 5
    registry.save_module(m)

    snap = collect_runtime_status(graph_store=store, registry=registry)
    assert snap.care_cycle.total_care_cycles == 5


# ---------------------------------------------------------------------------
# OmniWorkerStatus
# ---------------------------------------------------------------------------


def test_omni_worker_none_when_not_provided(tmp_path):
    store = _make_store(tmp_path)
    registry = _make_registry(tmp_path)
    snap = collect_runtime_status(graph_store=store, registry=registry)
    assert snap.omni_worker is None


def test_omni_worker_status_from_stopped_worker(tmp_path, monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)

    store = _make_store(tmp_path)
    registry = _make_registry(tmp_path)

    # Import here to isolate path manipulation side-effects to this test.
    from omni.qwen_omni_worker import QwenOmniWorker

    worker = QwenOmniWorker(
        graph_store=store,
        cycle_interval_s=30.0,
        min_store_resonance_score=0.25,
    )

    snap = collect_runtime_status(graph_store=store, registry=registry, omni_worker=worker)
    ow = snap.omni_worker

    assert isinstance(ow, OmniWorkerStatus)
    assert ow.running is False
    assert ow.realtime_enabled is False
    assert ow.cycle_interval_s == 30.0
    assert ow.min_store_resonance_score == 0.25


def test_omni_worker_status_duck_typed(tmp_path):
    """collect_runtime_status accepts any object with the expected attributes."""

    class _FakeWorker:
        _thread = None
        realtime_enabled = True
        cycle_interval_s = 15.0
        min_store_resonance_score = 0.4

    store = _make_store(tmp_path)
    registry = _make_registry(tmp_path)
    snap = collect_runtime_status(graph_store=store, registry=registry, omni_worker=_FakeWorker())

    ow = snap.omni_worker
    assert ow is not None
    assert ow.realtime_enabled is True
    assert ow.cycle_interval_s == 15.0
    assert ow.min_store_resonance_score == 0.4
    assert ow.running is False


# ---------------------------------------------------------------------------
# RuntimeStatusSnapshot shape and serialisation
# ---------------------------------------------------------------------------


def test_snapshot_is_frozen(tmp_path):
    store = _make_store(tmp_path)
    registry = _make_registry(tmp_path)
    snap = collect_runtime_status(graph_store=store, registry=registry)

    import pytest

    with pytest.raises((AttributeError, TypeError)):
        snap.captured_at = "tampered"  # type: ignore[misc]


def test_snapshot_to_dict_keys(tmp_path):
    store = _make_store(tmp_path)
    registry = _make_registry(tmp_path)
    snap = collect_runtime_status(graph_store=store, registry=registry)
    d = snap.to_dict()

    assert set(d.keys()) == {"captured_at", "graph_memory", "care_cycle", "omni_worker"}
    assert isinstance(d["captured_at"], str)
    assert isinstance(d["graph_memory"], dict)
    assert isinstance(d["care_cycle"], dict)
    assert d["omni_worker"] is None


def test_snapshot_to_dict_with_omni(tmp_path, monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)

    store = _make_store(tmp_path)
    registry = _make_registry(tmp_path)

    from omni.qwen_omni_worker import QwenOmniWorker

    worker = QwenOmniWorker(graph_store=store)
    snap = collect_runtime_status(graph_store=store, registry=registry, omni_worker=worker)
    d = snap.to_dict()

    assert isinstance(d["omni_worker"], dict)
    assert "running" in d["omni_worker"]
    assert "realtime_enabled" in d["omni_worker"]


def test_snapshot_captured_at_is_iso8601(tmp_path):
    from datetime import datetime

    store = _make_store(tmp_path)
    registry = _make_registry(tmp_path)
    snap = collect_runtime_status(graph_store=store, registry=registry)
    # Should parse without error.
    datetime.fromisoformat(snap.captured_at)


def test_snapshot_is_instance_of_runtime_status_snapshot(tmp_path):
    store = _make_store(tmp_path)
    registry = _make_registry(tmp_path)
    snap = collect_runtime_status(graph_store=store, registry=registry)
    assert isinstance(snap, RuntimeStatusSnapshot)
