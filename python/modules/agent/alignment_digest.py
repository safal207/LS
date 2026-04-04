# -*- coding: utf-8 -*-
"""Per-session alignment digest builder.

Deterministic, read-only aggregation over accumulated AlignmentMemoryUnits.
No LLM, no routing side-effects, no persistence.  Output is a compact,
JSON-serializable dict suitable for logs, API responses, and future UI.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from agent.alignment_memory import AlignmentMemoryUnit  # type: ignore[import]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _top_counts(values: list[str], n: int = 5) -> list[dict[str, Any]]:
    """Return top-N most common values as [{"value": ..., "count": ...}]."""
    if not values:
        return []
    return [
        {"value": v, "count": c}
        for v, c in Counter(values).most_common(n)
    ]


# ---------------------------------------------------------------------------
# Digest builder (pure, deterministic)
# ---------------------------------------------------------------------------

_EMPTY_DIGEST: dict[str, Any] = {
    "total_units": 0,
    "hotspots_top": [],
    "mismatch_reasons_top": [],
    "softening_signals_top": [],
    "effect_reasons_top": [],
    "guidance_applied_count": 0,
    "guidance_effective_count": 0,
    "softening_detected_count": 0,
    "avg_response_score": 0.0,
    "avg_goal_alignment_score": 0.0,
    "avg_tension_score_before": 0.0,
    "effective_rate": 0.0,
    "top_success_patterns": [],
}


def build_alignment_digest(
    units: list[AlignmentMemoryUnit],
    *,
    top_n: int = 5,
) -> dict[str, Any]:
    """Build a compact, explainable session digest from alignment memory units.

    Args:
        units: List of AlignmentMemoryUnit instances (read-only, not mutated).
        top_n: Maximum entries in every top-list (default 5).

    Returns:
        A stable dict with fixed keys.  All values are JSON-serializable.
        Returns the empty-digest template when units is empty.
    """
    if not units:
        return dict(_EMPTY_DIGEST)

    total = len(units)

    # Accumulate flat lists for counting
    hotspots: list[str] = []
    mismatch_reasons: list[str] = []
    softening_signals: list[str] = []
    effect_reasons: list[str] = []
    success_patterns: list[str] = []

    guidance_applied = 0
    guidance_effective = 0
    softening_detected = 0

    response_score_sum = 0.0
    goal_alignment_sum = 0.0
    tension_before_sum = 0.0
    tension_before_count = 0

    for u in units:
        if u.alignment_hotspot:
            hotspots.append(u.alignment_hotspot)
        mismatch_reasons.extend(u.mismatch_reasons)
        softening_signals.extend(u.softening_signals)
        if u.effect_reason:
            effect_reasons.append(u.effect_reason)

        if u.guidance_applied:
            guidance_applied += 1
        if u.guidance_effective:
            guidance_effective += 1
            # Success pattern = readable compound label
            parts: list[str] = []
            if u.alignment_hotspot:
                parts.append(u.alignment_hotspot)
            if u.effect_reason:
                parts.append(u.effect_reason)
            if parts:
                success_patterns.append(" | ".join(parts))
        if u.softening_detected:
            softening_detected += 1

        response_score_sum += u.response_score
        goal_alignment_sum += u.goal_alignment_score
        if u.tension_score_before is not None:
            tension_before_sum += u.tension_score_before
            tension_before_count += 1

    effective_rate = round(guidance_effective / guidance_applied, 3) if guidance_applied else 0.0
    avg_response = round(response_score_sum / total, 3)
    avg_goal = round(goal_alignment_sum / total, 3)
    avg_tension = round(tension_before_sum / tension_before_count, 3) if tension_before_count else 0.0

    return {
        "total_units": total,
        "hotspots_top": _top_counts(hotspots, top_n),
        "mismatch_reasons_top": _top_counts(mismatch_reasons, top_n),
        "softening_signals_top": _top_counts(softening_signals, top_n),
        "effect_reasons_top": _top_counts(effect_reasons, top_n),
        "guidance_applied_count": guidance_applied,
        "guidance_effective_count": guidance_effective,
        "softening_detected_count": softening_detected,
        "avg_response_score": avg_response,
        "avg_goal_alignment_score": avg_goal,
        "avg_tension_score_before": avg_tension,
        "effective_rate": effective_rate,
        "top_success_patterns": _top_counts(success_patterns, top_n),
    }


# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------

_DIGEST_KEYS = frozenset(build_alignment_digest([]).keys())


@dataclass
class AlignmentDigestMetrics:
    """Lightweight aggregate counters for digest build calls."""

    calls_total: int = 0
    empty_total: int = 0
    nonempty_total: int = 0
    units_processed_total: int = 0

    @property
    def avg_units_per_digest(self) -> float:
        if self.calls_total == 0:
            return 0.0
        return round(self.units_processed_total / self.calls_total, 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls_total": self.calls_total,
            "empty_total": self.empty_total,
            "nonempty_total": self.nonempty_total,
            "units_processed_total": self.units_processed_total,
            "avg_units_per_digest": self.avg_units_per_digest,
        }
