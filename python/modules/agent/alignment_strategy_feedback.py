# -*- coding: utf-8 -*-
"""Alignment strategy outcome feedback — deterministic post-cycle feedback layer.

After each cycle, records whether strategy recommendations were effective,
neutral, or ineffective based on the alignment outcome signals already present
in the pipeline.  Advisory-only read layer: never modifies routing, graph_mode,
route_key, reuse/refine/full_run, recommendations, or any upstream state.
No LLM, no embeddings, no auto-weight-updates.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Deterministic label policy
# ---------------------------------------------------------------------------

_EFFECTIVE_RESPONSE_SCORE_THRESHOLD = 0.65
_INEFFECTIVE_RESPONSE_SCORE_THRESHOLD = 0.35
_EFFECTIVE_GOAL_ALIGNMENT_THRESHOLD = 0.6


def _label_strategy_feedback(alignment_outcome: dict[str, Any]) -> str:
    """Return 'effective' | 'neutral' | 'ineffective' from deterministic signals.

    Priority order:
    1. Any explicit positive boolean signal → effective
    2. Any score above threshold → effective
    3. Any explicit low score → ineffective
    4. Otherwise → neutral
    """
    if not alignment_outcome:
        return "neutral"

    softening = bool(alignment_outcome.get("softening_detected"))
    guidance_ok = bool(alignment_outcome.get("guidance_effective"))
    response_score = float(alignment_outcome.get("response_score") or 0.0)
    goal_score = float(alignment_outcome.get("goal_alignment_score") or 0.0)

    # Positive signals take precedence
    if softening or guidance_ok:
        return "effective"
    if (
        response_score >= _EFFECTIVE_RESPONSE_SCORE_THRESHOLD
        or goal_score >= _EFFECTIVE_GOAL_ALIGNMENT_THRESHOLD
    ):
        return "effective"

    # Explicit weak outcome
    if (
        response_score > 0.0 and response_score < _INEFFECTIVE_RESPONSE_SCORE_THRESHOLD
    ):
        return "ineffective"

    return "neutral"


def _build_feedback_notes(
    label: str,
    alignment_outcome: dict[str, Any],
    recommendation: dict[str, Any],
) -> str:
    """Return a short, explainable human-readable notes string."""
    hotspot = recommendation.get("hotspot") or alignment_outcome.get("hotspot") or ""
    effect_reason = (
        alignment_outcome.get("effect_reason")
        or recommendation.get("effect_reason")
        or ""
    )

    if label == "effective":
        if alignment_outcome.get("softening_detected"):
            base = "recommendation aligned with a cycle where softening was detected"
        elif alignment_outcome.get("guidance_effective"):
            base = "recommendation aligned with a cycle where guidance was effective"
        else:
            base = "recommendation aligned with a high-score cycle"
    elif label == "ineffective":
        base = "recommendation present but cycle outcome was weak"
    else:
        base = "recommendation present; outcome shows no strong positive or negative signal"

    if hotspot:
        base += f" (hotspot: {hotspot})"
    if effect_reason:
        base += f"; effect: {effect_reason}"
    return base


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------

def build_strategy_outcome_feedback(
    recommendations: list[dict[str, Any]],
    alignment_outcome: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build one feedback object per recommendation for the current cycle.

    All feedback objects share the same label and score fields — the outcome
    is one per cycle, not per recommendation.  Each feedback object records
    which recommendation was active so callers can aggregate per strategy_id.

    Never raises; returns [] on bad input.
    """
    if not recommendations or not isinstance(recommendations, list):
        return []
    if not alignment_outcome or not isinstance(alignment_outcome, dict):
        return [_empty_feedback(rec) for rec in recommendations if isinstance(rec, dict)]

    label = _label_strategy_feedback(alignment_outcome)

    result: list[dict[str, Any]] = []
    for rec in recommendations:
        if not isinstance(rec, dict):
            continue
        notes = _build_feedback_notes(label, alignment_outcome, rec)
        feedback: dict[str, Any] = {
            "strategy_id": rec.get("strategy_id") or "",
            "pattern_ids": list(rec.get("based_on_pattern_ids") or []),
            "was_presented": True,
            "was_effective": label == "effective",
            "feedback_label": label,
            "effect_reason": (
                alignment_outcome.get("effect_reason")
                or rec.get("effect_reason")
                or ""
            ),
            "softening_detected": bool(alignment_outcome.get("softening_detected")),
            "guidance_effective": bool(alignment_outcome.get("guidance_effective")),
            "response_score": float(alignment_outcome.get("response_score") or 0.0),
            "goal_alignment_score": float(
                alignment_outcome.get("goal_alignment_score") or 0.0
            ),
            "notes": notes,
        }
        result.append(feedback)
    return result


def _empty_feedback(rec: dict[str, Any]) -> dict[str, Any]:
    """Feedback stub when alignment_outcome is unavailable."""
    return {
        "strategy_id": rec.get("strategy_id") or "",
        "pattern_ids": list(rec.get("based_on_pattern_ids") or []),
        "was_presented": True,
        "was_effective": False,
        "feedback_label": "neutral",
        "effect_reason": "",
        "softening_detected": False,
        "guidance_effective": False,
        "response_score": 0.0,
        "goal_alignment_score": 0.0,
        "notes": "no alignment outcome available for this cycle",
    }


# ---------------------------------------------------------------------------
# Summary aggregator
# ---------------------------------------------------------------------------

def build_strategy_feedback_summary(
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate a session's feedback events into a compact summary dict.

    Always returns the same fixed keys (JSON-serialisable, 0-value defaults).
    Never raises.
    """
    empty: dict[str, Any] = {
        "total_feedback_events": 0,
        "effective_total": 0,
        "neutral_total": 0,
        "ineffective_total": 0,
        "top_effective_strategy_ids": [],
        "top_ineffective_strategy_ids": [],
        "top_effective_pattern_ids": [],
        "avg_response_score": 0.0,
        "avg_goal_alignment_score": 0.0,
        "softening_positive_rate": 0.0,
    }
    if not events or not isinstance(events, list):
        return dict(empty)

    valid = [e for e in events if isinstance(e, dict)]
    if not valid:
        return dict(empty)

    total = len(valid)
    effective_total = sum(1 for e in valid if e.get("feedback_label") == "effective")
    neutral_total = sum(1 for e in valid if e.get("feedback_label") == "neutral")
    ineffective_total = sum(
        1 for e in valid if e.get("feedback_label") == "ineffective"
    )

    response_scores = [float(e.get("response_score") or 0.0) for e in valid]
    goal_scores = [float(e.get("goal_alignment_score") or 0.0) for e in valid]
    softening_count = sum(1 for e in valid if e.get("softening_detected"))

    avg_response = sum(response_scores) / total if total else 0.0
    avg_goal = sum(goal_scores) / total if total else 0.0
    softening_rate = softening_count / total if total else 0.0

    # Count strategy_id occurrences per label
    eff_sid_counts: dict[str, int] = {}
    ineff_sid_counts: dict[str, int] = {}
    eff_pid_counts: dict[str, int] = {}

    for e in valid:
        sid = e.get("strategy_id") or ""
        label = e.get("feedback_label") or "neutral"
        if sid:
            if label == "effective":
                eff_sid_counts[sid] = eff_sid_counts.get(sid, 0) + 1
            elif label == "ineffective":
                ineff_sid_counts[sid] = ineff_sid_counts.get(sid, 0) + 1
        if label == "effective":
            for pid in (e.get("pattern_ids") or []):
                if pid:
                    eff_pid_counts[pid] = eff_pid_counts.get(pid, 0) + 1

    top_effective_sids = [
        k for k, _ in sorted(eff_sid_counts.items(), key=lambda x: -x[1])[:5]
    ]
    top_ineffective_sids = [
        k for k, _ in sorted(ineff_sid_counts.items(), key=lambda x: -x[1])[:5]
    ]
    top_effective_pids = [
        k for k, _ in sorted(eff_pid_counts.items(), key=lambda x: -x[1])[:5]
    ]

    return {
        "total_feedback_events": total,
        "effective_total": effective_total,
        "neutral_total": neutral_total,
        "ineffective_total": ineffective_total,
        "top_effective_strategy_ids": top_effective_sids,
        "top_ineffective_strategy_ids": top_ineffective_sids,
        "top_effective_pattern_ids": top_effective_pids,
        "avg_response_score": round(avg_response, 4),
        "avg_goal_alignment_score": round(avg_goal, 4),
        "softening_positive_rate": round(softening_rate, 4),
    }


# ---------------------------------------------------------------------------
# Observability metrics
# ---------------------------------------------------------------------------

@dataclass
class AlignmentStrategyFeedbackMetrics:
    calls_total: int = 0
    recommendations_processed_total: int = 0
    feedback_events_total: int = 0
    effective_total: int = 0
    neutral_total: int = 0
    ineffective_total: int = 0
    summary_calls_total: int = 0

    @property
    def avg_feedback_per_call(self) -> float:
        if self.calls_total == 0:
            return 0.0
        return self.feedback_events_total / self.calls_total

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls_total": self.calls_total,
            "recommendations_processed_total": self.recommendations_processed_total,
            "feedback_events_total": self.feedback_events_total,
            "effective_total": self.effective_total,
            "neutral_total": self.neutral_total,
            "ineffective_total": self.ineffective_total,
            "summary_calls_total": self.summary_calls_total,
            "avg_feedback_per_call": self.avg_feedback_per_call,
        }
