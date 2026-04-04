# -*- coding: utf-8 -*-
"""Machine-readable runtime status snapshot for the live cognitive subsystems.

Covers:
  - graph_memory  (MemoryGraphStore: cases, resonance units, relational snapshots)
  - care_cycle    (DerivedModuleRegistry: module states, scores, cycle counts)
  - omni_worker   (QwenOmniWorker: running state, realtime flag, config)

Usage::

    from graph.runtime_snapshot import collect_runtime_status

    snapshot = collect_runtime_status(
        graph_store=store,
        registry=registry,
        omni_worker=worker,   # optional
    )
    print(snapshot.to_dict())
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from .derived_module_registry import DerivedModuleRegistry
from .memory_store import MemoryGraphStore


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Sub-status dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GraphMemoryStatus:
    """Counters and quality metrics for the persistent memory store."""

    total_cases: int
    total_resonance_units: int
    total_relational_snapshots: int
    avg_resonance_score: float
    avg_alignment_score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CareCycleStatus:
    """Aggregated health of derived modules tracked by the care cycle."""

    total_modules: int
    active: int
    review: int
    retired: int
    avg_trust_score: float
    avg_quality_score: float
    total_care_cycles: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OmniWorkerStatus:
    """Observed state of the QwenOmniWorker background daemon."""

    running: bool
    realtime_enabled: bool
    cycle_interval_s: float
    min_store_resonance_score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuntimeStatusSnapshot:
    """Top-level machine-readable snapshot of all live cognitive subsystems."""

    captured_at: str
    graph_memory: GraphMemoryStatus
    care_cycle: CareCycleStatus
    omni_worker: Optional[OmniWorkerStatus]

    def to_dict(self) -> dict[str, Any]:
        return {
            "captured_at": self.captured_at,
            "graph_memory": self.graph_memory.to_dict(),
            "care_cycle": self.care_cycle.to_dict(),
            "omni_worker": self.omni_worker.to_dict() if self.omni_worker is not None else None,
        }


# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------


def _collect_graph_memory(store: MemoryGraphStore) -> GraphMemoryStatus:
    cases = store.list_cases()
    units = store.list_resonance_units()
    snapshots = store.list_relational_snapshots()

    if units:
        avg_res = sum(u.resonance_score for u in units) / len(units)
        avg_ali = sum(u.alignment_score for u in units) / len(units)
    else:
        avg_res = 0.0
        avg_ali = 0.0

    return GraphMemoryStatus(
        total_cases=len(cases),
        total_resonance_units=len(units),
        total_relational_snapshots=len(snapshots),
        avg_resonance_score=round(avg_res, 4),
        avg_alignment_score=round(avg_ali, 4),
    )


def _collect_care_cycle(registry: DerivedModuleRegistry) -> CareCycleStatus:
    modules = registry.list_modules()
    state_counts: dict[str, int] = {"active": 0, "review": 0, "retired": 0}
    for m in modules:
        state_counts[m.state] = state_counts.get(m.state, 0) + 1

    if modules:
        avg_trust = sum(m.trust_score for m in modules) / len(modules)
        avg_quality = sum(m.quality_score for m in modules) / len(modules)
        total_cycles = sum(m.care_cycles for m in modules)
    else:
        avg_trust = 0.0
        avg_quality = 0.0
        total_cycles = 0

    return CareCycleStatus(
        total_modules=len(modules),
        active=state_counts.get("active", 0),
        review=state_counts.get("review", 0),
        retired=state_counts.get("retired", 0),
        avg_trust_score=round(avg_trust, 4),
        avg_quality_score=round(avg_quality, 4),
        total_care_cycles=total_cycles,
    )


def _collect_omni_worker(worker: Any) -> OmniWorkerStatus:
    """Extract status from a QwenOmniWorker instance via duck typing."""
    thread = getattr(worker, "_thread", None)
    running = bool(thread is not None and getattr(thread, "is_alive", lambda: False)())
    return OmniWorkerStatus(
        running=running,
        realtime_enabled=bool(getattr(worker, "realtime_enabled", False)),
        cycle_interval_s=float(getattr(worker, "cycle_interval_s", 0.0)),
        min_store_resonance_score=float(getattr(worker, "min_store_resonance_score", 0.0)),
    )


def collect_runtime_status(
    *,
    graph_store: MemoryGraphStore,
    registry: DerivedModuleRegistry,
    omni_worker: Any | None = None,
) -> RuntimeStatusSnapshot:
    """Build and return a machine-readable snapshot of all live subsystems.

    Args:
        graph_store: The active MemoryGraphStore instance.
        registry:    The active DerivedModuleRegistry instance.
        omni_worker: Optional QwenOmniWorker instance (duck-typed, no hard import).

    Returns:
        A frozen RuntimeStatusSnapshot.
    """
    return RuntimeStatusSnapshot(
        captured_at=_utc_now(),
        graph_memory=_collect_graph_memory(graph_store),
        care_cycle=_collect_care_cycle(registry),
        omni_worker=_collect_omni_worker(omni_worker) if omni_worker is not None else None,
    )
