# -*- coding: utf-8 -*-
"""Alignment strategy reputation overlay — advisory confidence/reputation layer.

Reads already-computed strategy aggregation and builds a compact, explainable
reputation overlay for each strategy recommendation.  Advisory-only read layer:
never modifies recommendations, aggregation, routing, graph_mode, route_key,
reuse/refine/full_run, or any upstream pipeline state.
No LLM, no embeddings, no auto-weight updates.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Thresholds (deterministic, fixed for MVP)
# ---------------------------------------------------------------------------

_VALIDATED_MIN_SUPPORT = 5
_VALIDATED_MIN_EFF_RATE = 0.6

_EMERGING_MIN_SUPPORT = 2
_EMERGING_MIN_EFF_RATE = 0.4   # some positive signal

_WEAK_MIN_SUPPORT = 3          # need at least some data to call it "weak"
_WEAK_MAX_EFF_RATE = 0.3       # consistently low

_MAX_CONFIDENCE = 1.0
_SUPPORT_CONFIDENCE_SCALE = 20  # support_count / scale, capped at 0.5


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_strategy_stats(
    strategy_id: str,
    strategy_stats: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for s in strategy_stats:
        if s.get("strategy_id") == strategy_id:
            return s
    return None


def _find_pattern_stats(
    pattern_id: str,
    pattern_stats: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for p in pattern_stats:
        if p.get("pattern_id") == pattern_id:
            return p
    return None


def _compute_reputation_confidence(
    strategy_stat: dict[str, Any] | None,
    linked_pattern_stats: list[dict[str, Any]],
) -> float:
    """Return advisory_confidence in [0.0, 1.0] from deterministic stats.

    Components:
    - support component:   min(support_count / scale, 0.5)
    - rate component:      effective_rate * 0.4
    - pattern bonus:       avg effective_rate of linked patterns * 0.1

    Returns 0.0 when no stats available.
    """
    if not strategy_stat:
        return 0.0

    support = int(strategy_stat.get("times_presented") or 0)
    eff_rate = float(strategy_stat.get("effective_rate") or 0.0)

    support_score = min(support / _SUPPORT_CONFIDENCE_SCALE, 0.5)
    rate_score = eff_rate * 0.4

    pattern_bonus = 0.0
    if linked_pattern_stats:
        pat_rates = [
            float(p.get("effective_rate") or 0.0)
            for p in linked_pattern_stats
        ]
        pattern_bonus = (sum(pat_rates) / len(pat_rates)) * 0.1

    return round(min(support_score + rate_score + pattern_bonus, _MAX_CONFIDENCE), 4)


def _label_strategy_reputation(
    strategy_stat: dict[str, Any] | None,
    linked_pattern_stats: list[dict[str, Any]],
) -> tuple[str, str, str]:
    """Return (reputation_label, reputation_reason, advisory_note).

    Labels (in priority order):
    - validated_pattern   — strong support + high effective rate
    - weak_pattern        — enough data but consistently low rate
    - emerging_pattern    — limited support but positive early signal
    - insufficient_data   — not enough evidence yet
    """
    if not strategy_stat:
        return (
            "insufficient_data",
            "not enough evidence yet",
            "needs more evidence before relying on this recommendation",
        )

    support = int(strategy_stat.get("times_presented") or 0)
    eff_rate = float(strategy_stat.get("effective_rate") or 0.0)

    # --- validated ---
    if support >= _VALIDATED_MIN_SUPPORT and eff_rate >= _VALIDATED_MIN_EFF_RATE:
        return (
            "validated_pattern",
            f"high effective rate ({eff_rate:.0%}) across {support} feedback events",
            "safe to keep as a strong advisory option",
        )

    # --- weak ---
    if support >= _WEAK_MIN_SUPPORT and eff_rate < _WEAK_MAX_EFF_RATE:
        return (
            "weak_pattern",
            f"repeated low-effect outcomes ({eff_rate:.0%} effective rate, {support} events)",
            "do not suppress automatically; use cautiously",
        )

    # --- emerging ---
    if support >= _EMERGING_MIN_SUPPORT and eff_rate >= _EMERGING_MIN_EFF_RATE:
        return (
            "emerging_pattern",
            f"limited support ({support} events) but positive early signal ({eff_rate:.0%})",
            "treat as provisional; promising but not yet validated",
        )

    # --- check if linked patterns are positive when strategy data is thin ---
    if support < _EMERGING_MIN_SUPPORT and linked_pattern_stats:
        avg_pat_rate = sum(
            float(p.get("effective_rate") or 0.0) for p in linked_pattern_stats
        ) / len(linked_pattern_stats)
        if avg_pat_rate >= _EMERGING_MIN_EFF_RATE:
            return (
                "emerging_pattern",
                f"strategy has minimal data but linked patterns show {avg_pat_rate:.0%} effective rate",
                "treat as provisional; pattern evidence is encouraging",
            )

    return (
        "insufficient_data",
        "not enough evidence yet",
        "needs more evidence before relying on this recommendation",
    )


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------

def build_strategy_reputation_overlay(
    recommendations: list[dict[str, Any]],
    aggregation: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build one reputation overlay object per recommendation.

    Never modifies recommendations or aggregation.  Never raises.
    Returns [] for empty/invalid inputs.
    """
    if not recommendations or not isinstance(recommendations, list):
        return []

    strategy_stats: list[dict[str, Any]] = []
    pattern_stats: list[dict[str, Any]] = []
    if isinstance(aggregation, dict):
        strategy_stats = aggregation.get("strategy_stats") or []
        pattern_stats = aggregation.get("pattern_stats") or []

    result: list[dict[str, Any]] = []
    for rec in recommendations:
        if not isinstance(rec, dict):
            continue

        sid = rec.get("strategy_id") or ""
        s_stat = _find_strategy_stats(sid, strategy_stats) if sid else None

        # Gather linked pattern stats
        linked_pids = list(rec.get("based_on_pattern_ids") or [])
        if s_stat:
            # Merge with strategy's own linked pattern ids (top 5)
            for pid in (s_stat.get("linked_pattern_ids_top") or []):
                if pid not in linked_pids:
                    linked_pids.append(pid)
        linked_p_stats = [
            p for p in [_find_pattern_stats(pid, pattern_stats) for pid in linked_pids]
            if p is not None
        ]

        label, reason, note = _label_strategy_reputation(s_stat, linked_p_stats)
        confidence = _compute_reputation_confidence(s_stat, linked_p_stats)

        overlay: dict[str, Any] = {
            "strategy_id": sid,
            "reputation_label": label,
            "advisory_confidence": confidence,
            "support_count": int(s_stat.get("times_presented") or 0) if s_stat else 0,
            "effective_rate": float(s_stat.get("effective_rate") or 0.0) if s_stat else 0.0,
            "linked_pattern_ids": linked_pids[:5],
            "reputation_reason": reason,
            "advisory_note": note,
            "has_pattern_evidence": bool(linked_p_stats),
        }
        result.append(overlay)

    return result


# ---------------------------------------------------------------------------
# Observability metrics
# ---------------------------------------------------------------------------

@dataclass
class AlignmentStrategyReputationMetrics:
    calls_total: int = 0
    recommendations_processed_total: int = 0
    validated_total: int = 0
    emerging_total: int = 0
    weak_total: int = 0
    insufficient_total: int = 0
    confidence_sum: float = 0.0
    pattern_evidence_total: int = 0
    strategy_only_evidence_total: int = 0

    @property
    def avg_confidence_score(self) -> float:
        if self.recommendations_processed_total == 0:
            return 0.0
        return round(
            self.confidence_sum / self.recommendations_processed_total, 4
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls_total": self.calls_total,
            "recommendations_processed_total": self.recommendations_processed_total,
            "validated_total": self.validated_total,
            "emerging_total": self.emerging_total,
            "weak_total": self.weak_total,
            "insufficient_total": self.insufficient_total,
            "avg_confidence_score": self.avg_confidence_score,
            "pattern_evidence_total": self.pattern_evidence_total,
            "strategy_only_evidence_total": self.strategy_only_evidence_total,
        }
