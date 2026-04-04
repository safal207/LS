# -*- coding: utf-8 -*-
"""Resonance Evolve Lite — controlled route evolution from repeated causal paths.

Aggregates high-quality ResonanceKnowledgeUnit causal paths into versioned
RouteSnapshot candidates.  A snapshot can be promoted (above a confidence
threshold) or rolled back — without ever touching live route selection until
explicitly promoted.

Algorithm
---------
1. **Group** units by intent (None → "unknown").
2. For each group with ≥ min_unit_count units:
   a. Identify *common steps* — causal-path steps whose ``strategy`` value
      appears in ≥ path_overlap_threshold fraction of units in the group.
   b. Build the aggregated_path from those common steps (order preserved from
      the first unit that contains them).
   c. Compute confidence = mean resonance_score of contributing units.
3. **Create or version** a RouteSnapshot for the group.  If a snapshot for
   the same intent already exists and the new confidence is higher, a new
   version is appended (old version is kept for rollback).
4. **Promote** a snapshot when confidence ≥ promote_threshold.
5. **Rollback** clears the promoted flag and records a reason.

No weights are modified, no model is touched.  A promoted snapshot is only
a *candidate* — callers decide how to use it in live routing.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class RouteEvolveConfig:
    """Configurable parameters for Resonance Evolve Lite.

    Attributes:
        min_unit_count:
            Minimum number of agreeing units required to form a candidate
            snapshot.  Default: 2.
        promote_threshold:
            Confidence (mean resonance score of group) at or above which a
            snapshot may be promoted.  Default: 0.7.
        path_overlap_threshold:
            Fraction of group units that must share a causal-path strategy
            for that step to be included in the aggregated path.  Default: 0.5.
    """

    min_unit_count: int = 2
    promote_threshold: float = 0.7
    path_overlap_threshold: float = 0.5


# ---------------------------------------------------------------------------
# RouteSnapshot dataclass
# ---------------------------------------------------------------------------


@dataclass
class RouteSnapshot:
    """Versioned candidate route aggregated from repeated resonance units.

    Attributes:
        snapshot_id:    Stable identifier shared across all versions of this
                        candidate (keyed by intent).
        version:        Incremented each time a newer aggregation replaces the
                        previous one for the same snapshot_id.
        intent:         The shared intent of the source units ("unknown" when None).
        why:            Most common ``why`` value among source units, or None.
        aggregated_path: Common causal-path steps extracted from source units.
        confidence:     Mean resonance_score of contributing units (0–1).
        source_unit_count: Number of units that contributed.
        source_unit_ids:   IDs of contributing units.
        promoted:       True when the snapshot has been explicitly promoted.
        created_at:     ISO-8601 UTC creation timestamp.
        promoted_at:    ISO-8601 UTC timestamp of the last promotion, or None.
        rolled_back:    True when a promoted snapshot was rolled back.
        rollback_reason: Human-readable reason for the rollback.
    """

    snapshot_id: str
    version: int
    intent: str
    why: Optional[str]
    aggregated_path: list[dict[str, Any]]
    confidence: float
    source_unit_count: int
    source_unit_ids: list[str]
    promoted: bool = False
    created_at: str = field(default_factory=_utc_now)
    promoted_at: Optional[str] = None
    rolled_back: bool = False
    rollback_reason: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RouteSnapshot":
        return cls(
            snapshot_id=str(data.get("snapshot_id") or str(uuid4())),
            version=int(data.get("version", 1) or 1),
            intent=str(data.get("intent") or "unknown"),
            why=data.get("why"),
            aggregated_path=list(data.get("aggregated_path") or []),
            confidence=float(data.get("confidence", 0.0) or 0.0),
            source_unit_count=int(data.get("source_unit_count", 0) or 0),
            source_unit_ids=list(data.get("source_unit_ids") or []),
            promoted=bool(data.get("promoted", False)),
            created_at=str(data.get("created_at") or _utc_now()),
            promoted_at=data.get("promoted_at"),
            rolled_back=bool(data.get("rolled_back", False)),
            rollback_reason=data.get("rollback_reason"),
        )


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def _dominant_why(units: list[Any]) -> Optional[str]:
    """Return the most common non-None why value among units."""
    counts: dict[str, int] = {}
    for u in units:
        why = str(getattr(u, "why", None) or "")
        if why:
            counts[why] = counts.get(why, 0) + 1
    if not counts:
        return None
    return max(counts, key=lambda k: counts[k])


def _aggregate_path(units: list[Any], overlap_threshold: float) -> list[dict[str, Any]]:
    """Extract causal-path steps shared by ≥ overlap_threshold of units.

    Steps are identified by their ``strategy`` key.  Order is taken from
    the first unit that contains each qualifying strategy.
    """
    if not units:
        return []

    # Collect strategy → frequency across all units.
    strategy_count: dict[str, int] = {}
    strategy_first_step: dict[str, dict[str, Any]] = {}

    for u in units:
        path = list(getattr(u, "causal_path", None) or [])
        seen_in_unit: set[str] = set()
        for step in path:
            if not isinstance(step, dict):
                continue
            strategy = str(step.get("strategy", "") or "")
            if not strategy or strategy in seen_in_unit:
                continue
            seen_in_unit.add(strategy)
            strategy_count[strategy] = strategy_count.get(strategy, 0) + 1
            if strategy not in strategy_first_step:
                strategy_first_step[strategy] = step

    # Use strict > so that overlap_threshold=0.5 with 2 units requires
    # a step to appear in both (count=2 > 1.0), not just one (count=1 > 1.0 fails).
    min_count = overlap_threshold * len(units)
    common = {s for s, c in strategy_count.items() if c > min_count}

    # Reconstruct ordered path from the first unit's sequence.
    first_path = list(getattr(units[0], "causal_path", None) or [])
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for step in first_path:
        if not isinstance(step, dict):
            continue
        strategy = str(step.get("strategy", "") or "")
        if strategy in common and strategy not in seen:
            result.append(dict(step))
            seen.add(strategy)

    # Append any common strategies not present in the first unit's path.
    for strategy in common - seen:
        result.append(dict(strategy_first_step[strategy]))

    return result


# ---------------------------------------------------------------------------
# RouteEvolver
# ---------------------------------------------------------------------------


class RouteEvolver:
    """Aggregates ResonanceKnowledgeUnits into versioned RouteSnapshot candidates.

    This class is stateless with respect to storage — it delegates persistence
    to the caller (typically ``MemoryGraphStore``).  The typical call sequence::

        evolver = RouteEvolver(config)
        snapshots = evolver.evolve(units, existing_snapshots)
        for snap in snapshots:
            store.store_route_snapshot(snap)

        # Later — promote if confidence is high enough:
        updated = evolver.promote(snap, existing_snapshots)

        # Or roll back a bad promotion:
        updated = evolver.rollback(snap, reason="caused regression")
    """

    def __init__(self, config: RouteEvolveConfig | None = None) -> None:
        self._config = config or RouteEvolveConfig()

    @property
    def config(self) -> RouteEvolveConfig:
        return self._config

    # ------------------------------------------------------------------
    # Core evolution
    # ------------------------------------------------------------------

    def evolve(
        self,
        units: list[Any],
        existing_snapshots: list[RouteSnapshot] | None = None,
    ) -> list[RouteSnapshot]:
        """Produce an updated list of RouteSnapshots from *units*.

        Only groups with ≥ config.min_unit_count units are processed.
        If a group already has a snapshot and the new aggregation yields
        higher confidence, a new version replaces it (version incremented).
        Snapshots for intents not present in *units* are returned unchanged.

        Args:
            units:              Source ResonanceKnowledgeUnit instances.
            existing_snapshots: Current stored snapshots (read for versioning).

        Returns:
            The complete updated snapshot list (old + new/updated).
        """
        existing = list(existing_snapshots or [])
        existing_by_intent: dict[str, RouteSnapshot] = {
            s.intent: s for s in existing
        }

        # Group units by intent.
        groups: dict[str, list[Any]] = {}
        for u in units:
            intent = str(getattr(u, "intent", None) or "unknown")
            groups.setdefault(intent, []).append(u)

        updated: dict[str, RouteSnapshot] = dict(existing_by_intent)

        for intent, group in groups.items():
            if len(group) < self._config.min_unit_count:
                logger.debug(
                    "RouteEvolver skipping intent=%r: only %d units (need %d)",
                    intent,
                    len(group),
                    self._config.min_unit_count,
                )
                continue

            confidence = sum(
                float(getattr(u, "resonance_score", 0.0) or 0.0) for u in group
            ) / len(group)

            existing_snap = existing_by_intent.get(intent)

            # Skip if existing snapshot already has equal-or-better confidence.
            if existing_snap is not None and not existing_snap.rolled_back:
                if existing_snap.confidence >= confidence:
                    continue

            unit_ids = [
                str(getattr(u, "unit_id", None) or "")
                for u in group
                if getattr(u, "unit_id", None)
            ]
            aggregated = _aggregate_path(group, self._config.path_overlap_threshold)

            if existing_snap is not None:
                new_snap = RouteSnapshot(
                    snapshot_id=existing_snap.snapshot_id,
                    version=existing_snap.version + 1,
                    intent=intent,
                    why=_dominant_why(group),
                    aggregated_path=aggregated,
                    confidence=round(confidence, 4),
                    source_unit_count=len(group),
                    source_unit_ids=unit_ids,
                    promoted=False,  # new version starts unpromoted
                    created_at=_utc_now(),
                )
            else:
                new_snap = RouteSnapshot(
                    snapshot_id=str(uuid4()),
                    version=1,
                    intent=intent,
                    why=_dominant_why(group),
                    aggregated_path=aggregated,
                    confidence=round(confidence, 4),
                    source_unit_count=len(group),
                    source_unit_ids=unit_ids,
                )

            updated[intent] = new_snap
            logger.debug(
                "RouteEvolver evolved intent=%r v%d confidence=%.3f units=%d",
                intent,
                new_snap.version,
                new_snap.confidence,
                len(group),
            )

        return list(updated.values())

    # ------------------------------------------------------------------
    # Promote / rollback
    # ------------------------------------------------------------------

    def promote(self, snapshot: RouteSnapshot) -> RouteSnapshot:
        """Promote *snapshot* if its confidence meets the threshold.

        Returns the updated snapshot (promoted=True) or the original if
        confidence is below the threshold or the snapshot is rolled back.
        """
        if snapshot.rolled_back:
            logger.debug(
                "RouteEvolver promote skipped: snapshot %s is rolled back",
                snapshot.snapshot_id,
            )
            return snapshot

        if snapshot.confidence < self._config.promote_threshold:
            logger.debug(
                "RouteEvolver promote skipped: confidence %.3f < threshold %.3f",
                snapshot.confidence,
                self._config.promote_threshold,
            )
            return snapshot

        return RouteSnapshot(
            **{**snapshot.to_dict(), "promoted": True, "promoted_at": _utc_now()}
        )

    def rollback(self, snapshot: RouteSnapshot, *, reason: str = "") -> RouteSnapshot:
        """Roll back a promoted snapshot.

        Clears the promoted flag and records the reason.  The snapshot is
        kept in storage (audit trail) but will not be returned by
        ``list_promoted_snapshots``.
        """
        return RouteSnapshot(
            **{
                **snapshot.to_dict(),
                "promoted": False,
                "rolled_back": True,
                "rollback_reason": str(reason),
            }
        )
