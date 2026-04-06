# -*- coding: utf-8 -*-
"""Alignment strategy recommender — deterministic advisory recommendation layer.

Builds 1–3 short explainable strategy recommendations from session-local
alignment success patterns and the current cycle's alignment context.

This module is advisory-only: it never modifies routing, graph_mode,
route_key, reuse/refine/full_run decisions, or any pipeline state.
No LLM, no embeddings, no fuzzy ranking.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Action lookup tables (deterministic, keyword-based)
# ---------------------------------------------------------------------------

_SIGNAL_ACTIONS: dict[str, list[str]] = {
    "bridge_phrase": [
        "acknowledge common ground before moving forward",
    ],
    "pacing_marker": [
        "slow response tempo and increase structural clarity",
    ],
    "acknowledgment": [
        "name the shared concern before proposing action",
    ],
    "proposal_framing": [
        "frame solutions as shared options, not unilateral decisions",
    ],
    "dialogue_invitation": [
        "invite the other party to respond before concluding",
    ],
    "dialogue_invitation_structural": [
        "use open-ended structure to invite co-ownership of the solution",
    ],
}

_HOTSPOT_KEYWORD_ACTIONS: list[tuple[str, str]] = [
    ("deadline", "separate urgency from importance before resolving"),
    ("quality", "distinguish quality standards from blocking concerns"),
    ("scope", "identify minimal viable agreement before broader discussion"),
    ("conflict", "acknowledge the mismatch before debating correctness"),
    ("velocity", "reduce pacing and increase clarity"),
    ("trust", "synchronize positions before suggesting action"),
    ("pressure", "name background pressure before addressing surface behavior"),
    ("alignment", "avoid winner/loser framing; focus on shared goal"),
]

_MISMATCH_KEYWORD_ACTIONS: list[tuple[str, str]] = [
    ("intent_conflict", "separate background cause from visible behavior"),
    ("direction", "avoid winner/loser framing; focus on shared goal"),
    ("expectation", "name the expectation gap before proposing resolution"),
    ("priority", "distinguish short-term urgency from long-term importance"),
]


# ---------------------------------------------------------------------------
# Scoring (pure, deterministic)
# ---------------------------------------------------------------------------


def _score_pattern_for_recommendation(
    pattern: dict[str, Any],
    *,
    current_hotspot: str,
    current_mismatch_reasons: list[str],
    current_intent: str,
) -> tuple[float, dict[str, bool]]:
    """Score a success pattern against the current cycle context.

    Returns (score, overlap_flags) where overlap_flags indicates which
    signals contributed (used for observability counters).
    """
    score = 0.0
    flags: dict[str, bool] = {
        "hotspot_overlap": False,
        "mismatch_overlap": False,
        "intent_match": False,
    }

    # Hotspot overlap (substring, both directions)
    ph = (pattern.get("hotspot") or "").lower()
    ch = current_hotspot.lower()
    if ph and ch and (ph in ch or ch in ph):
        score += 0.4
        flags["hotspot_overlap"] = True

    # Mismatch reason overlap (token intersection)
    pattern_reasons = set(pattern.get("mismatch_reasons") or [])
    current_reasons = set(current_mismatch_reasons)
    reason_overlap = pattern_reasons & current_reasons
    if reason_overlap:
        overlap_ratio = len(reason_overlap) / max(len(pattern_reasons), 1)
        score += 0.3 * min(overlap_ratio, 1.0)
        flags["mismatch_overlap"] = True

    # Guard: intent and bonuses only apply when there is at least one text
    # match (hotspot or mismatch overlap). This prevents high-efficacy
    # unrelated patterns from surfacing via intent/bonus signals alone
    # (same pattern as in alignment_memory retrieval).
    if score == 0.0:
        return 0.0, flags

    # Intent match — check effect_reason and mismatch_reasons only (not hotspot,
    # to avoid substring collisions between intent and hotspot tokens).
    if current_intent:
        ci = current_intent.lower()
        effect_text = (pattern.get("effect_reason") or "").lower()
        if ci in effect_text or any(
            ci in r.lower() for r in (pattern.get("mismatch_reasons") or [])
        ):
            score += 0.15
            flags["intent_match"] = True

    # Support and effectiveness bonuses (small, tie-breaking only).
    # Use uncapped linear scale so support=2 vs support=15 are distinguishable.
    score += int(pattern.get("support_count") or 0) * 0.005
    score += float(pattern.get("effective_rate") or 0.0) * 0.1

    return min(score, 1.0), flags


# ---------------------------------------------------------------------------
# Action builder (deterministic)
# ---------------------------------------------------------------------------


def _build_recommended_actions(pattern: dict[str, Any]) -> list[str]:
    """Derive 1–3 short advisory actions from a pattern's signals and hotspot."""
    actions: list[str] = []

    # From softening signals
    for sig in pattern.get("softening_signals") or []:
        for action in _SIGNAL_ACTIONS.get(sig, []):
            if action not in actions:
                actions.append(action)

    # From hotspot keywords
    hotspot = (pattern.get("hotspot") or "").lower()
    for keyword, action in _HOTSPOT_KEYWORD_ACTIONS:
        if keyword in hotspot and action not in actions:
            actions.append(action)

    # From mismatch reason keywords
    for reason in pattern.get("mismatch_reasons") or []:
        rl = reason.lower()
        for keyword, action in _MISMATCH_KEYWORD_ACTIONS:
            if keyword in rl and action not in actions:
                actions.append(action)

    # Generic fallback if still empty but guidance was effective
    if not actions and float(pattern.get("effective_rate") or 0.0) > 0.5:
        actions.append("apply alignment guidance before direct response")

    return actions[:3]  # cap at 3


# ---------------------------------------------------------------------------
# Title / summary builders (deterministic)
# ---------------------------------------------------------------------------


def _build_title(pattern: dict[str, Any]) -> str:
    hotspot = pattern.get("hotspot")
    effect = pattern.get("effect_reason")
    if effect:
        # Trim to first clause (before ' →' or ' ->' for readability)
        short = effect.split("→")[0].split("->")[0].strip()
        return f"Use {short}" if short else "Apply alignment strategy"
    if hotspot:
        return f"Reduce tension in {hotspot!r} context"
    return "Apply alignment strategy"


def _build_summary(pattern: dict[str, Any]) -> str:
    n = int(pattern.get("support_count") or 0)
    rate = float(pattern.get("effective_rate") or 0.0)
    hotspot = pattern.get("hotspot") or "alignment"
    pct = int(rate * 100)
    return (
        f"In {n} similar {hotspot!r} cycle(s), this approach was effective "
        f"{pct}% of the time."
    )


# ---------------------------------------------------------------------------
# Main builder (pure, deterministic)
# ---------------------------------------------------------------------------


def build_alignment_strategy_recommendations(
    patterns: list[dict[str, Any]],
    *,
    alignment_report: dict[str, Any] | None = None,
    intent: str | None = None,
    max_results: int = 3,
    min_score: float = 0.15,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build 1–max_results strategy recommendations from session success patterns.

    Args:
        patterns:         Alignment success patterns (from build_alignment_success_patterns).
        alignment_report: Current cycle alignment report (optional context).
        intent:           Current cycle intent string (optional context).
        max_results:      Maximum recommendations to return (default 3).
        min_score:        Minimum relevance score to include a pattern.

    Returns:
        (recommendations, overlap_stats) where overlap_stats is used by the
        caller to update observability metrics.
    """
    if not patterns:
        return [], {"considered": 0, "filtered": 0, "hotspot_hits": 0,
                    "mismatch_hits": 0, "intent_hits": 0}

    # Extract current context from alignment_report
    report = alignment_report or {}
    current_hotspot = ""
    current_mismatch: list[str] = []
    if isinstance(report, dict):
        hotspots = report.get("pairwise_hotspots") or []
        if hotspots and isinstance(hotspots[0], dict):
            current_hotspot = str(hotspots[0].get("tension_axis") or "")
        current_mismatch = [str(r) for r in (report.get("mismatch_reasons") or [])]

    current_intent = (intent or "").strip()

    scored: list[tuple[float, dict[str, bool], dict[str, Any]]] = []
    for p in patterns:
        score, flags = _score_pattern_for_recommendation(
            p,
            current_hotspot=current_hotspot,
            current_mismatch_reasons=current_mismatch,
            current_intent=current_intent,
        )
        scored.append((score, flags, p))

    considered = len(scored)
    filtered = sum(1 for s, _, _ in scored if s < min_score)
    hotspot_hits = sum(1 for _, f, _ in scored if f["hotspot_overlap"])
    mismatch_hits = sum(1 for _, f, _ in scored if f["mismatch_overlap"])
    intent_hits = sum(1 for _, f, _ in scored if f["intent_match"])

    qualifying = [(s, f, p) for s, f, p in scored if s >= min_score]
    qualifying.sort(key=lambda x: x[0], reverse=True)

    recommendations: list[dict[str, Any]] = []
    for score, flags, pattern in qualifying[:max_results]:
        actions = _build_recommended_actions(pattern)
        strategy_id = hashlib.sha1(
            (pattern.get("pattern_id") or "").encode()
        ).hexdigest()[:10]

        recommendations.append({
            "strategy_id": strategy_id,
            "title": _build_title(pattern),
            "summary": _build_summary(pattern),
            "hotspot": pattern.get("hotspot"),
            "based_on_pattern_ids": [pattern.get("pattern_id") or ""],
            "support_count": int(pattern.get("support_count") or 0),
            "effective_rate": float(pattern.get("effective_rate") or 0.0),
            "recommended_actions": actions,
        })

    return recommendations, {
        "considered": considered,
        "filtered": filtered,
        "hotspot_hits": hotspot_hits,
        "mismatch_hits": mismatch_hits,
        "intent_hits": intent_hits,
    }


# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------


@dataclass
class AlignmentStrategyRecommendationMetrics:
    """Lightweight counters for strategy recommendation builds."""

    calls_total: int = 0
    empty_total: int = 0
    nonempty_total: int = 0
    patterns_considered_total: int = 0
    patterns_filtered_total: int = 0
    recommendations_built_total: int = 0
    hotspot_overlap_total: int = 0
    mismatch_overlap_total: int = 0
    intent_match_total: int = 0

    @property
    def avg_recommendations_per_call(self) -> float:
        if self.calls_total == 0:
            return 0.0
        return round(self.recommendations_built_total / self.calls_total, 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls_total": self.calls_total,
            "empty_total": self.empty_total,
            "nonempty_total": self.nonempty_total,
            "patterns_considered_total": self.patterns_considered_total,
            "patterns_filtered_total": self.patterns_filtered_total,
            "recommendations_built_total": self.recommendations_built_total,
            "hotspot_overlap_total": self.hotspot_overlap_total,
            "mismatch_overlap_total": self.mismatch_overlap_total,
            "intent_match_total": self.intent_match_total,
            "avg_recommendations_per_call": self.avg_recommendations_per_call,
        }
