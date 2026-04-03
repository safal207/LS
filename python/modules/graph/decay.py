# -*- coding: utf-8 -*-
"""Radioactive decay model for ResonanceKnowledgeUnit scores.

Each resonance unit has an effective score that fades over time using the
standard radioactive decay formula:

    effective(t) = score₀ · e^(−λ · Δt)

where:
    λ   = ln(2) / half_life          (decay constant)
    Δt  = elapsed time in hours since the unit was last confirmed
    score₀ = stored resonance_score

Half-lives are configurable per source so that different quality tiers
age at different rates:

    source          | default T½
    ----------------|-----------
    care_cycle      | 72 h   (trusted, long-lived)
    dashscope       | 48 h   (realtime, medium)
    dashscope_realtime | 48 h
    qwen_omni_worker | 24 h  (background, standard)
    fallback        | 12 h   (noisy, short-lived)
    *               | 24 h   (catch-all)

A unit whose effective score drops below ``floor_score`` is considered
**expired** and can be safely pruned from the active working set.

"Confirming" a unit (e.g. when a successful route reuses it) refreshes its
``timestamp`` via ``MemoryGraphStore.confirm_resonance_unit()``, resetting
the decay clock and granting a full half-life extension.

No changes to the ``ResonanceKnowledgeUnit`` dataclass are required —
the decay is computed purely from the stored ``resonance_score``,
``timestamp``, and ``metadata["source"]``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Default half-lives (hours) per source identifier
# ---------------------------------------------------------------------------

_DEFAULT_HALF_LIVES: dict[str, float] = {
    "care_cycle": 72.0,
    "dashscope": 48.0,
    "dashscope_realtime": 48.0,
    "qwen_omni_worker": 24.0,
    "fallback": 12.0,
    "mvp_fallback": 12.0,
}

_DEFAULT_HALF_LIFE_HOURS: float = 24.0
_DEFAULT_FLOOR_SCORE: float = 0.05


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class ResonanceDecayConfig:
    """Configurable decay parameters.

    Attributes:
        default_half_life_hours:
            Half-life used when the unit's source is not in
            ``half_life_by_source``.  Default: 24 hours.
        half_life_by_source:
            Maps ``metadata["source"]`` → half-life in hours.
            Callers may override individual entries or add new ones.
        floor_score:
            Effective score below which a unit is considered expired.
            Default: 0.05.
    """

    default_half_life_hours: float = _DEFAULT_HALF_LIFE_HOURS
    half_life_by_source: dict[str, float] = field(
        default_factory=lambda: dict(_DEFAULT_HALF_LIVES)
    )
    floor_score: float = _DEFAULT_FLOOR_SCORE

    def half_life_for(self, source: str) -> float:
        """Return the half-life (hours) appropriate for *source*."""
        return self.half_life_by_source.get(source, self.default_half_life_hours)


# ---------------------------------------------------------------------------
# Core decay computation
# ---------------------------------------------------------------------------


def _parse_timestamp(ts: str) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp string; return None on failure."""
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def _elapsed_hours(timestamp: str, now: datetime) -> float:
    """Return hours elapsed since *timestamp*; 0.0 on parse error."""
    dt = _parse_timestamp(timestamp)
    if dt is None:
        return 0.0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    return max(0.0, delta.total_seconds() / 3600.0)


def effective_score(
    unit: Any,
    config: ResonanceDecayConfig,
    *,
    now: Optional[datetime] = None,
) -> float:
    """Compute the effective resonance score after radioactive decay.

    Formula::

        effective = score₀ · exp(−λ · Δt)
        λ = ln(2) / T½

    Args:
        unit:   Any object with ``resonance_score`` (float), ``timestamp``
                (ISO-8601 str), and optionally ``metadata`` (dict with
                ``"source"`` key).
        config: Decay configuration.
        now:    Reference time; defaults to UTC now.

    Returns:
        A float in [0.0, score₀].
    """
    if now is None:
        now = datetime.now(timezone.utc)

    score0 = float(getattr(unit, "resonance_score", 0.0) or 0.0)
    if score0 <= 0.0:
        return 0.0

    timestamp = str(getattr(unit, "timestamp", "") or "")
    metadata: dict[str, Any] = dict(getattr(unit, "metadata", None) or {})
    source = str(metadata.get("source", "") or "")

    half_life = config.half_life_for(source)
    if half_life <= 0.0:
        return 0.0

    elapsed = _elapsed_hours(timestamp, now)
    decay_constant = math.log(2) / half_life
    return score0 * math.exp(-decay_constant * elapsed)


def is_expired(
    unit: Any,
    config: ResonanceDecayConfig,
    *,
    now: Optional[datetime] = None,
) -> bool:
    """Return True if the unit's effective score is below the floor."""
    return effective_score(unit, config, now=now) < config.floor_score


# ---------------------------------------------------------------------------
# Batch helpers
# ---------------------------------------------------------------------------


def apply_decay(
    units: list[Any],
    config: ResonanceDecayConfig,
    *,
    now: Optional[datetime] = None,
) -> list[tuple[Any, float]]:
    """Return ``(unit, effective_score)`` pairs, sorted strongest-first.

    Expired units (below ``config.floor_score``) are **included** — callers
    decide whether to prune.  Use :func:`prune_expired` if you want only the
    live set.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    scored = [(u, effective_score(u, config, now=now)) for u in units]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def prune_expired(
    units: list[Any],
    config: ResonanceDecayConfig,
    *,
    now: Optional[datetime] = None,
) -> list[Any]:
    """Return only units whose effective score is at or above the floor."""
    if now is None:
        now = datetime.now(timezone.utc)
    return [u for u in units if not is_expired(u, config, now=now)]
