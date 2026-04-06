# -*- coding: utf-8 -*-
"""Alignment success patterns — lightweight deterministic pattern extraction.

Groups repeated successful alignment cycles from AlignmentMemoryUnits into
compact, explainable reusable patterns.  No ML, no embeddings, no LLM.
Purely a read/debug layer — never modifies routing, graph_mode, or any
pipeline state.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from agent.alignment_memory import AlignmentMemoryUnit  # type: ignore[import]


# ---------------------------------------------------------------------------
# Grouping key
# ---------------------------------------------------------------------------


def make_alignment_pattern_key(unit: AlignmentMemoryUnit) -> str:
    """Build a deterministic grouping key from a unit's explainable fields.

    Components:
        - alignment_hotspot (normalised lower-case, or "")
        - sorted, deduped mismatch_reasons
        - sorted, deduped softening_signals

    Returns a short hex digest so the key is safe as a dict key / JSON value.
    """
    hotspot = (unit.alignment_hotspot or "").lower().strip()
    reasons = "|".join(sorted(set(unit.mismatch_reasons)))
    signals = "|".join(sorted(set(unit.softening_signals)))
    raw = f"{hotspot}::{reasons}::{signals}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def _is_success(unit: AlignmentMemoryUnit) -> bool:
    """Return True if the unit represents a successful alignment cycle."""
    return bool(
        unit.guidance_effective
        or unit.softening_detected
        or unit.effect_reason
    )


# ---------------------------------------------------------------------------
# Pattern builder (pure, deterministic)
# ---------------------------------------------------------------------------


def build_alignment_success_patterns(
    units: list[AlignmentMemoryUnit],
    *,
    min_support: int = 2,
) -> list[dict[str, Any]]:
    """Extract repeated successful alignment patterns from session memory.

    Args:
        units:       List of AlignmentMemoryUnit instances (read-only).
        min_support: Minimum number of matching units to form a pattern.
                     Default 2 — single occurrences are too weak to be
                     considered a pattern.

    Returns:
        List of compact, JSON-serializable pattern dicts, sorted by
        support_count descending.  Empty list when no patterns qualify.
    """
    if not units:
        return []

    # Group successful units by deterministic key
    groups: dict[str, list[AlignmentMemoryUnit]] = defaultdict(list)
    for u in units:
        if _is_success(u):
            key = make_alignment_pattern_key(u)
            groups[key].append(u)

    patterns: list[dict[str, Any]] = []
    for pattern_id, group in groups.items():
        if len(group) < min_support:
            continue

        support = len(group)
        effective_count = sum(1 for u in group if u.guidance_effective)
        softening_count = sum(1 for u in group if u.softening_detected)
        response_avg = round(sum(u.response_score for u in group) / support, 3)
        goal_avg = round(sum(u.goal_alignment_score for u in group) / support, 3)

        # Representative unit — highest response_score
        rep = max(group, key=lambda u: u.response_score)

        # Compact mismatch reasons and signals (deduped, sorted, capped)
        all_reasons: list[str] = []
        all_signals: list[str] = []
        for u in group:
            all_reasons.extend(u.mismatch_reasons)
            all_signals.extend(u.softening_signals)
        top_reasons = sorted(set(all_reasons))[:5]
        top_signals = sorted(set(all_signals))[:5]

        # Effect reason label — most common non-empty
        effect_labels = [u.effect_reason for u in group if u.effect_reason]
        effect_reason = _most_common(effect_labels)

        # Example strategy summary from representative unit
        strategy_parts: list[str] = []
        if rep.alignment_hotspot:
            strategy_parts.append(f"hotspot={rep.alignment_hotspot!r}")
        if top_signals:
            strategy_parts.append(f"signals=[{', '.join(top_signals[:3])}]")
        if effect_reason:
            strategy_parts.append(effect_reason)
        example_strategy = "; ".join(strategy_parts) if strategy_parts else None

        patterns.append({
            "pattern_id": pattern_id,
            "hotspot": rep.alignment_hotspot,
            "mismatch_reasons": top_reasons,
            "softening_signals": top_signals,
            "effect_reason": effect_reason,
            "support_count": support,
            "effective_rate": round(effective_count / support, 3),
            "softening_rate": round(softening_count / support, 3),
            "avg_response_score": response_avg,
            "avg_goal_alignment_score": goal_avg,
            "example_strategy_summary": example_strategy,
        })

    patterns.sort(key=lambda p: p["support_count"], reverse=True)
    return patterns


def _most_common(values: list[str]) -> str | None:
    """Return the most frequently occurring value, or None if empty."""
    if not values:
        return None
    counts: dict[str, int] = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    return max(counts, key=lambda k: counts[k])


# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------


@dataclass
class AlignmentSuccessPatternMetrics:
    """Lightweight counters for alignment success pattern builds."""

    calls_total: int = 0
    units_processed_total: int = 0
    patterns_built_total: int = 0
    patterns_skipped_total: int = 0
    patterns_with_hotspot: int = 0
    patterns_with_softening: int = 0

    @property
    def avg_units_per_pattern(self) -> float:
        if self.patterns_built_total == 0:
            return 0.0
        return round(self.units_processed_total / self.patterns_built_total, 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls_total": self.calls_total,
            "units_processed_total": self.units_processed_total,
            "patterns_built_total": self.patterns_built_total,
            "patterns_skipped_total": self.patterns_skipped_total,
            "patterns_with_hotspot": self.patterns_with_hotspot,
            "patterns_with_softening": self.patterns_with_softening,
            "avg_units_per_pattern": self.avg_units_per_pattern,
        }
