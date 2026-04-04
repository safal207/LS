# -*- coding: utf-8 -*-
"""Alignment strategy feedback aggregation — per-pattern and per-strategy
reputation summary layer.

Aggregates session-local strategy feedback events into compact, explainable
per-pattern and per-strategy statistics.  Read-only: never modifies feedback
events, recommender state, routing, graph_mode, or any upstream pipeline state.
No LLM, no embeddings, no auto-weight updates.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Per-pattern aggregation
# ---------------------------------------------------------------------------

def build_pattern_feedback_stats(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return one stats dict per unique pattern_id seen across feedback events.

    Each event may carry multiple pattern_ids; each is counted independently.
    Output is sorted by times_recommended descending.  Never raises.
    """
    if not events or not isinstance(events, list):
        return []

    # pattern_id -> accumulator
    acc: dict[str, dict[str, Any]] = {}

    for ev in events:
        if not isinstance(ev, dict):
            continue
        label = ev.get("feedback_label") or "neutral"
        response = float(ev.get("response_score") or 0.0)
        goal = float(ev.get("goal_alignment_score") or 0.0)
        softening = bool(ev.get("softening_detected"))
        sid = ev.get("strategy_id") or ""

        for pid in (ev.get("pattern_ids") or []):
            if not pid:
                continue
            if pid not in acc:
                acc[pid] = {
                    "_times": 0,
                    "_effective": 0,
                    "_neutral": 0,
                    "_ineffective": 0,
                    "_softening": 0,
                    "_response_sum": 0.0,
                    "_goal_sum": 0.0,
                    "_last_label": "neutral",
                    "_strategy_ids": {},
                }
            a = acc[pid]
            a["_times"] += 1
            if label == "effective":
                a["_effective"] += 1
            elif label == "ineffective":
                a["_ineffective"] += 1
            else:
                a["_neutral"] += 1
            if softening:
                a["_softening"] += 1
            a["_response_sum"] += response
            a["_goal_sum"] += goal
            a["_last_label"] = label
            if sid:
                a["_strategy_ids"][sid] = a["_strategy_ids"].get(sid, 0) + 1

    result = []
    for pid, a in acc.items():
        n = a["_times"]
        top_sids = [
            k for k, _ in sorted(
                a["_strategy_ids"].items(), key=lambda x: -x[1]
            )[:5]
        ]
        result.append({
            "pattern_id": pid,
            "times_recommended": n,
            "effective_total": a["_effective"],
            "neutral_total": a["_neutral"],
            "ineffective_total": a["_ineffective"],
            "effective_rate": round(a["_effective"] / n, 4) if n else 0.0,
            "softening_positive_rate": round(a["_softening"] / n, 4) if n else 0.0,
            "avg_response_score": round(a["_response_sum"] / n, 4) if n else 0.0,
            "avg_goal_alignment_score": round(a["_goal_sum"] / n, 4) if n else 0.0,
            "last_feedback_label": a["_last_label"],
            "linked_strategy_ids_top": top_sids,
        })

    result.sort(key=lambda x: -x["times_recommended"])
    return result


# ---------------------------------------------------------------------------
# Per-strategy aggregation
# ---------------------------------------------------------------------------

def build_strategy_feedback_stats(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return one stats dict per unique strategy_id seen across feedback events.

    Output is sorted by times_presented descending.  Never raises.
    """
    if not events or not isinstance(events, list):
        return []

    acc: dict[str, dict[str, Any]] = {}

    for ev in events:
        if not isinstance(ev, dict):
            continue
        sid = ev.get("strategy_id") or ""
        if not sid:
            continue
        label = ev.get("feedback_label") or "neutral"
        response = float(ev.get("response_score") or 0.0)
        goal = float(ev.get("goal_alignment_score") or 0.0)

        if sid not in acc:
            acc[sid] = {
                "_times": 0,
                "_effective": 0,
                "_neutral": 0,
                "_ineffective": 0,
                "_response_sum": 0.0,
                "_goal_sum": 0.0,
                "_last_label": "neutral",
                "_pattern_ids": {},
            }
        a = acc[sid]
        a["_times"] += 1
        if label == "effective":
            a["_effective"] += 1
        elif label == "ineffective":
            a["_ineffective"] += 1
        else:
            a["_neutral"] += 1
        a["_response_sum"] += response
        a["_goal_sum"] += goal
        a["_last_label"] = label
        for pid in (ev.get("pattern_ids") or []):
            if pid:
                a["_pattern_ids"][pid] = a["_pattern_ids"].get(pid, 0) + 1

    result = []
    for sid, a in acc.items():
        n = a["_times"]
        top_pids = [
            k for k, _ in sorted(
                a["_pattern_ids"].items(), key=lambda x: -x[1]
            )[:5]
        ]
        result.append({
            "strategy_id": sid,
            "times_presented": n,
            "effective_total": a["_effective"],
            "neutral_total": a["_neutral"],
            "ineffective_total": a["_ineffective"],
            "effective_rate": round(a["_effective"] / n, 4) if n else 0.0,
            "avg_response_score": round(a["_response_sum"] / n, 4) if n else 0.0,
            "avg_goal_alignment_score": round(a["_goal_sum"] / n, 4) if n else 0.0,
            "linked_pattern_ids_top": top_pids,
            "last_feedback_label": a["_last_label"],
        })

    result.sort(key=lambda x: -x["times_presented"])
    return result


# ---------------------------------------------------------------------------
# Global summary
# ---------------------------------------------------------------------------

_TOP_N = 5


def build_strategy_feedback_aggregation_summary(
    events: list[dict[str, Any]],
    *,
    top_n: int = _TOP_N,
) -> dict[str, Any]:
    """Return a compact global summary over pattern- and strategy-level stats.

    Fixed-key output; all values are JSON-serialisable.  Never raises.
    """
    empty: dict[str, Any] = {
        "total_patterns_seen": 0,
        "total_strategies_seen": 0,
        "top_effective_patterns": [],
        "top_ineffective_patterns": [],
        "top_effective_strategies": [],
        "top_ineffective_strategies": [],
        "global_effective_rate": 0.0,
        "global_softening_positive_rate": 0.0,
    }
    if not events or not isinstance(events, list):
        return dict(empty)

    pat_stats = build_pattern_feedback_stats(events)
    strat_stats = build_strategy_feedback_stats(events)

    if not pat_stats and not strat_stats:
        return dict(empty)

    # Global rates over all events
    valid = [e for e in events if isinstance(e, dict)]
    total = len(valid)
    effective_count = sum(1 for e in valid if e.get("feedback_label") == "effective")
    softening_count = sum(1 for e in valid if e.get("softening_detected"))
    global_eff_rate = round(effective_count / total, 4) if total else 0.0
    global_soft_rate = round(softening_count / total, 4) if total else 0.0

    top_eff_pats = [
        p["pattern_id"]
        for p in sorted(pat_stats, key=lambda x: -x["effective_rate"])[:top_n]
        if p["effective_total"] > 0
    ]
    top_ineff_pats = [
        p["pattern_id"]
        for p in sorted(pat_stats, key=lambda x: -x["ineffective_total"])[:top_n]
        if p["ineffective_total"] > 0
    ]
    top_eff_strats = [
        s["strategy_id"]
        for s in sorted(strat_stats, key=lambda x: -x["effective_rate"])[:top_n]
        if s["effective_total"] > 0
    ]
    top_ineff_strats = [
        s["strategy_id"]
        for s in sorted(strat_stats, key=lambda x: -x["ineffective_total"])[:top_n]
        if s["ineffective_total"] > 0
    ]

    return {
        "total_patterns_seen": len(pat_stats),
        "total_strategies_seen": len(strat_stats),
        "top_effective_patterns": top_eff_pats,
        "top_ineffective_patterns": top_ineff_pats,
        "top_effective_strategies": top_eff_strats,
        "top_ineffective_strategies": top_ineff_strats,
        "global_effective_rate": global_eff_rate,
        "global_softening_positive_rate": global_soft_rate,
    }


# ---------------------------------------------------------------------------
# Observability metrics
# ---------------------------------------------------------------------------

@dataclass
class AlignmentStrategyAggregationMetrics:
    calls_total: int = 0
    events_processed_total: int = 0
    unique_patterns_total: int = 0
    unique_strategies_total: int = 0
    empty_total: int = 0
    nonempty_total: int = 0

    @property
    def avg_events_per_pattern(self) -> float:
        if self.unique_patterns_total == 0:
            return 0.0
        return self.events_processed_total / self.unique_patterns_total

    @property
    def avg_events_per_strategy(self) -> float:
        if self.unique_strategies_total == 0:
            return 0.0
        return self.events_processed_total / self.unique_strategies_total

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls_total": self.calls_total,
            "events_processed_total": self.events_processed_total,
            "unique_patterns_total": self.unique_patterns_total,
            "unique_strategies_total": self.unique_strategies_total,
            "empty_total": self.empty_total,
            "nonempty_total": self.nonempty_total,
            "avg_events_per_pattern": self.avg_events_per_pattern,
            "avg_events_per_strategy": self.avg_events_per_strategy,
        }
