# -*- coding: utf-8 -*-
"""Deterministic strategy calibration summary (read-only explainability layer)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_CALIBRATION_LABELS = (
    "well_calibrated",
    "promising_but_thin",
    "recommended_but_not_adopted",
    "adopted_but_low_outcome",
    "weakly_calibrated",
    "insufficient_data",
)


@dataclass
class AlignmentStrategyCalibrationMetrics:
    calls_total: int = 0
    strategies_processed_total: int = 0
    well_calibrated_total: int = 0
    promising_but_thin_total: int = 0
    recommended_but_not_adopted_total: int = 0
    adopted_but_low_outcome_total: int = 0
    weakly_calibrated_total: int = 0
    insufficient_data_total: int = 0
    _adoption_rate_sum: float = 0.0
    _effective_rate_sum: float = 0.0

    @property
    def avg_adoption_rate(self) -> float:
        if self.calls_total == 0:
            return 0.0
        return self._adoption_rate_sum / self.calls_total

    @property
    def avg_effective_rate(self) -> float:
        if self.calls_total == 0:
            return 0.0
        return self._effective_rate_sum / self.calls_total

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls_total": self.calls_total,
            "strategies_processed_total": self.strategies_processed_total,
            "well_calibrated_total": self.well_calibrated_total,
            "promising_but_thin_total": self.promising_but_thin_total,
            "recommended_but_not_adopted_total": self.recommended_but_not_adopted_total,
            "adopted_but_low_outcome_total": self.adopted_but_low_outcome_total,
            "weakly_calibrated_total": self.weakly_calibrated_total,
            "insufficient_data_total": self.insufficient_data_total,
            "avg_adoption_rate": round(self.avg_adoption_rate, 4),
            "avg_effective_rate": round(self.avg_effective_rate, 4),
        }


_METRICS = AlignmentStrategyCalibrationMetrics()


def get_alignment_strategy_calibration_metrics() -> dict[str, Any]:
    return _METRICS.to_dict()


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _build_calibration_reason(stats: dict[str, Any]) -> str:
    label = stats.get("calibration_label") or "insufficient_data"
    if label == "well_calibrated":
        return "frequently adopted and followed by strong outcomes"
    if label == "promising_but_thin":
        return "positive signal exists but support is still small"
    if label == "recommended_but_not_adopted":
        return "recommended often but rarely reflected in final responses"
    if label == "adopted_but_low_outcome":
        return "reflected in responses, but outcomes stayed weak"
    if label == "weakly_calibrated":
        return "adoption and outcomes are both weak"
    return "not enough evidence yet"


def _label_strategy_calibration(stats: dict[str, Any]) -> str:
    recs = int(stats.get("times_recommended") or 0)
    adopted = int(stats.get("times_adopted") or 0)
    evidence = (
        recs
        + int(stats.get("effective_total") or 0)
        + int(stats.get("neutral_total") or 0)
        + int(stats.get("ineffective_total") or 0)
    )
    adoption_rate = _safe_float(stats.get("adoption_rate"))
    effective_rate = _safe_float(stats.get("effective_rate"))

    if evidence == 0:
        return "insufficient_data"
    if recs >= 3 and adoption_rate < 0.25:
        return "recommended_but_not_adopted"
    if adopted >= 2 and effective_rate < 0.4:
        return "adopted_but_low_outcome"
    if adopted >= 2 and adoption_rate >= 0.6 and effective_rate >= 0.6:
        return "well_calibrated"
    if evidence <= 3 and adoption_rate >= 0.5 and effective_rate >= 0.5:
        return "promising_but_thin"
    if evidence >= 2 and adoption_rate < 0.4 and effective_rate < 0.4:
        return "weakly_calibrated"
    if evidence <= 1:
        return "insufficient_data"
    return "weakly_calibrated"




def _iter_aggregation_strategy_rows(aggregation: dict[str, Any] | None) -> list[tuple[str, dict[str, Any]]]:
    """Normalize aggregation["strategy_stats"] into (strategy_id, row) tuples."""
    if not isinstance(aggregation, dict):
        return []
    stats = aggregation.get("strategy_stats") or {}
    if isinstance(stats, dict):
        out: list[tuple[str, dict[str, Any]]] = []
        for sid, row in stats.items():
            if sid and isinstance(row, dict):
                out.append((str(sid), row))
        return out
    if isinstance(stats, list):
        out = []
        for row in stats:
            if not isinstance(row, dict):
                continue
            sid = str(row.get("strategy_id") or row.get("id") or "").strip()
            if sid:
                out.append((sid, row))
        return out
    return []

def build_per_strategy_calibration_stats(
    recommendations: list[dict[str, Any]],
    feedback_events: list[dict[str, Any]],
    adoption_traces: list[dict[str, Any]],
    aggregation: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    per: dict[str, dict[str, Any]] = {}

    def ensure(sid: str) -> dict[str, Any]:
        if sid not in per:
            per[sid] = {
                "strategy_id": sid,
                "times_recommended": 0,
                "times_adopted": 0,
                "times_partially_adopted": 0,
                "times_not_adopted": 0,
                "adoption_rate": 0.0,
                "effective_total": 0,
                "neutral_total": 0,
                "ineffective_total": 0,
                "effective_rate": 0.0,
                "avg_adoption_score": 0.0,
                "avg_response_score": 0.0,
                "avg_goal_alignment_score": 0.0,
                "reputation_label": "unknown",
                "calibration_label": "insufficient_data",
                "calibration_reason": "not enough evidence yet",
                "linked_pattern_ids_top": [],
                "_adoption_score_sum": 0.0,
                "_adoption_score_count": 0,
                "_response_sum": 0.0,
                "_goal_sum": 0.0,
                "_feedback_count": 0,
                "_pattern_counts": {},
            }
        return per[sid]

    for rec in recommendations or []:
        if not isinstance(rec, dict):
            continue
        sid = str(rec.get("strategy_id") or "").strip()
        if not sid:
            continue
        row = ensure(sid)
        row["times_recommended"] += 1
        for pid in rec.get("based_on_pattern_ids") or []:
            if not pid:
                continue
            counts = row["_pattern_counts"]
            counts[pid] = counts.get(pid, 0) + 1

    for tr in adoption_traces or []:
        if not isinstance(tr, dict):
            continue
        sid = str(tr.get("strategy_id") or "").strip()
        if not sid:
            continue
        row = ensure(sid)
        label = str(tr.get("adoption_label") or "not_adopted")
        if label == "adopted":
            row["times_adopted"] += 1
        elif label == "partially_adopted":
            row["times_partially_adopted"] += 1
        else:
            row["times_not_adopted"] += 1
        score = _safe_float(tr.get("adoption_score"))
        row["_adoption_score_sum"] += score
        row["_adoption_score_count"] += 1

    for ev in feedback_events or []:
        if not isinstance(ev, dict):
            continue
        sid = str(ev.get("strategy_id") or "").strip()
        if not sid:
            continue
        row = ensure(sid)
        label = str(ev.get("feedback_label") or "neutral")
        if label == "effective":
            row["effective_total"] += 1
        elif label == "ineffective":
            row["ineffective_total"] += 1
        else:
            row["neutral_total"] += 1
        row["_response_sum"] += _safe_float(ev.get("response_score"))
        row["_goal_sum"] += _safe_float(ev.get("goal_alignment_score"))
        row["_feedback_count"] += 1
        for pid in ev.get("pattern_ids") or []:
            if not pid:
                continue
            counts = row["_pattern_counts"]
            counts[pid] = counts.get(pid, 0) + 1

    for sid, agg in _iter_aggregation_strategy_rows(aggregation):
        row = ensure(sid)
        if agg.get("reputation_label"):
            row["reputation_label"] = str(agg.get("reputation_label"))

    rows = []
    for sid in sorted(per.keys()):
        row = per[sid]
        ad_total = row["times_adopted"] + row["times_partially_adopted"] + row["times_not_adopted"]
        row["adoption_rate"] = round((row["times_adopted"] + 0.5 * row["times_partially_adopted"]) / ad_total, 4) if ad_total else 0.0
        fb_total = row["effective_total"] + row["neutral_total"] + row["ineffective_total"]
        row["effective_rate"] = round(row["effective_total"] / fb_total, 4) if fb_total else 0.0
        row["avg_adoption_score"] = round(row["_adoption_score_sum"] / row["_adoption_score_count"], 4) if row["_adoption_score_count"] else 0.0
        row["avg_response_score"] = round(row["_response_sum"] / row["_feedback_count"], 4) if row["_feedback_count"] else 0.0
        row["avg_goal_alignment_score"] = round(row["_goal_sum"] / row["_feedback_count"], 4) if row["_feedback_count"] else 0.0
        pcounts = row["_pattern_counts"]
        row["linked_pattern_ids_top"] = [pid for pid, _ in sorted(pcounts.items(), key=lambda x: (-x[1], x[0]))[:5]]
        row["calibration_label"] = _label_strategy_calibration(row)
        row["calibration_reason"] = _build_calibration_reason(row)
        for k in [
            "_adoption_score_sum",
            "_adoption_score_count",
            "_response_sum",
            "_goal_sum",
            "_feedback_count",
            "_pattern_counts",
        ]:
            row.pop(k, None)
        rows.append(row)
    return rows


def build_strategy_calibration_overview(
    per_strategy: list[dict[str, Any]],
    *,
    top_k: int = 3,
) -> dict[str, Any]:
    counts = {k: 0 for k in _CALIBRATION_LABELS}
    for row in per_strategy:
        label = row.get("calibration_label")
        if label in counts:
            counts[label] += 1

    def top_ids(rows: list[dict[str, Any]], key: str, reverse: bool = True) -> list[str]:
        ranked = sorted(rows, key=lambda r: (_safe_float(r.get(key)), str(r.get("strategy_id"))), reverse=reverse)
        return [str(r.get("strategy_id")) for r in ranked[:top_k]]

    well_rows = [r for r in per_strategy if r.get("calibration_label") == "well_calibrated"]
    under_rows = [r for r in per_strategy if r.get("calibration_label") == "recommended_but_not_adopted"]
    low_rows = [r for r in per_strategy if r.get("calibration_label") == "adopted_but_low_outcome"]

    return {
        "total_strategies_seen": len(per_strategy),
        "well_calibrated_total": counts["well_calibrated"],
        "promising_total": counts["promising_but_thin"],
        "recommended_but_not_adopted_total": counts["recommended_but_not_adopted"],
        "adopted_but_low_outcome_total": counts["adopted_but_low_outcome"],
        "weakly_calibrated_total": counts["weakly_calibrated"],
        "insufficient_total": counts["insufficient_data"],
        "top_well_calibrated_strategies": top_ids(well_rows, "effective_rate", reverse=True),
        "top_underadopted_strategies": top_ids(under_rows, "times_recommended", reverse=True),
        "top_low_outcome_strategies": top_ids(low_rows, "effective_rate", reverse=False),
    }


def build_strategy_calibration_summary(
    recommendations: list[dict[str, Any]],
    feedback_events: list[dict[str, Any]],
    adoption_traces: list[dict[str, Any]],
    aggregation: dict[str, Any] | None = None,
    *,
    top_k: int = 3,
) -> dict[str, Any]:
    per_strategy = build_per_strategy_calibration_stats(
        recommendations,
        feedback_events,
        adoption_traces,
        aggregation,
    )
    overview = build_strategy_calibration_overview(per_strategy, top_k=top_k)

    _METRICS.calls_total += 1
    _METRICS.strategies_processed_total += len(per_strategy)
    _METRICS.well_calibrated_total += overview["well_calibrated_total"]
    _METRICS.promising_but_thin_total += overview["promising_total"]
    _METRICS.recommended_but_not_adopted_total += overview["recommended_but_not_adopted_total"]
    _METRICS.adopted_but_low_outcome_total += overview["adopted_but_low_outcome_total"]
    _METRICS.weakly_calibrated_total += overview["weakly_calibrated_total"]
    _METRICS.insufficient_data_total += overview["insufficient_total"]
    avg_adoption = sum(_safe_float(r.get("adoption_rate")) for r in per_strategy) / len(per_strategy) if per_strategy else 0.0
    avg_effective = sum(_safe_float(r.get("effective_rate")) for r in per_strategy) / len(per_strategy) if per_strategy else 0.0
    _METRICS._adoption_rate_sum += avg_adoption
    _METRICS._effective_rate_sum += avg_effective

    return {
        "overview": overview,
        "per_strategy": per_strategy,
        "metrics": _METRICS.to_dict(),
    }
