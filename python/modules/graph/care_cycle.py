from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

from .derived_module_registry import DerivedModuleRegistry
from .evolve import RouteEvolver
from .memory_store import MemoryGraphStore
from .models import DerivedModule, ResonanceKnowledgeUnit

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CareCycleResult:
    module_id: str
    action: str
    state: str
    trust_score: float
    quality_score: float
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


class CareCycleRunner:
    def __init__(
        self,
        registry: DerivedModuleRegistry,
        graph_store: MemoryGraphStore | None = None,
        *,
        min_quality: float = 0.68,
        min_trust: float = 0.58,
        retire_trust: float = 0.35,
        promote_bonus: float = 0.03,
        demote_penalty: float = 0.08,
        resonance_unit_threshold: float = 0.3,
        route_evolver: RouteEvolver | None = None,
    ) -> None:
        self.registry = registry
        self.graph_store = graph_store
        self.min_quality = min_quality
        self.min_trust = min_trust
        self.retire_trust = retire_trust
        self.promote_bonus = promote_bonus
        self.demote_penalty = demote_penalty
        self.resonance_unit_threshold = resonance_unit_threshold
        self.route_evolver = route_evolver

    def review(
        self,
        module: DerivedModule | str,
        *,
        cycle_id: str | None = None,
        source_question: str | None = None,
        intent: str | None = None,
        why: str | None = None,
        goal_vector: list[float] | None = None,
        causal_path: list[dict] | None = None,
        resonance_score: float | None = None,
        alignment_score: float | None = None,
    ) -> Optional[CareCycleResult]:
        current = self.registry.get_module(module) if isinstance(module, str) else module
        if current is None:
            return None

        action = "keep"
        reason = "stable"

        if current.trust_score <= self.retire_trust or (current.runs >= 3 and current.successes == 0):
            current.state = "retired"
            current.trust_score = round(max(0.0, current.trust_score - self.demote_penalty), 4)
            action = "retire"
            reason = "low-trust-or-zero-success"
        elif current.quality_score < self.min_quality or current.trust_score < self.min_trust:
            current.state = "review"
            current.trust_score = round(max(0.0, current.trust_score - self.demote_penalty), 4)
            action = "demote"
            reason = "quality-or-trust-below-threshold"
        else:
            current.state = "active"
            current.trust_score = round(min(1.0, current.trust_score + self.promote_bonus), 4)
            action = "promote" if current.runs > 0 else "keep"
            reason = "healthy-module"

        current.care_cycles += 1
        current.last_reviewed_at = _utc_now()
        saved = self.registry.save_module(current)
        if (
            self.graph_store is not None
            and source_question
            and saved.state == "active"
            and action in {"keep", "promote"}
            and float(resonance_score or 0.0) > self.resonance_unit_threshold
        ):
            unit = ResonanceKnowledgeUnit(
                source_question=source_question,
                intent=intent,
                why=why,
                goal_vector=list(goal_vector or []),
                causal_path=list(causal_path or []),
                resonance_score=float(resonance_score or 0.0),
                alignment_score=float(alignment_score or 0.0),
                metadata={"source": "care_cycle", "cycle_id": cycle_id},
            )
            try:
                self.graph_store.store_resonance_unit(unit)
            except Exception as exc:
                logger.debug("CareCycleRunner resonance unit store skipped: %s", exc)

            if self.route_evolver is not None:
                try:
                    live_units = self.graph_store.list_live_resonance_units()
                    existing = self.graph_store.list_route_snapshots()
                    updated = self.route_evolver.evolve(live_units, existing)
                    for snap in updated:
                        snap = self.route_evolver.promote(snap)
                        self.graph_store.store_route_snapshot(snap)
                except Exception as exc:
                    logger.debug("CareCycleRunner route evolution skipped: %s", exc)
        return CareCycleResult(
            module_id=saved.module_id,
            action=action,
            state=saved.state,
            trust_score=saved.trust_score,
            quality_score=saved.quality_score,
            reason=reason,
        )
