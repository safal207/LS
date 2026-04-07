from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from .council_sync import quality_score_from_council_outcome
from .merit_sync import build_merit_updates_from_council_ledger


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _round(value: float) -> float:
    return round(float(value), 4)


def _as_namespace(value: Any) -> Any:
    if isinstance(value, dict):
        return SimpleNamespace(**{key: _as_namespace(item) for key, item in value.items()})
    if isinstance(value, list):
        return [_as_namespace(item) for item in value]
    return value


def load_council_ledgers(artifacts_dir: str | Path) -> list[dict[str, Any]]:
    directory = Path(artifacts_dir)
    if not directory.exists():
        return []

    ledgers: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict) and payload.get("cycle_id"):
            ledgers.append(payload)
    return ledgers


def summarize_council_ledgers(ledgers: list[dict[str, Any]]) -> dict[str, Any]:
    if not ledgers:
        return {
            "ledger_count": 0,
            "summary": {
                "success_rate": 0.0,
                "average_receiver_resonance": 0.0,
                "average_path_quality": 0.0,
                "average_network_improvement": 0.0,
                "average_merit_score": 0.0,
                "top_best_contributor_model_id": None,
            },
            "histograms": {
                "best_contributor_counts": [],
                "cumulative_contribution_scores": [],
                "model_type_average_contribution": [],
                "route_wins": [],
            },
            "trends": {
                "receiver_resonance": [],
                "path_quality": [],
                "network_improvement": [],
                "quality_score": [],
                "average_merit_score": [],
            },
            "cycles": [],
        }

    best_contributor_counts: dict[str, int] = {}
    cumulative_contribution_scores: dict[str, float] = {}
    model_type_totals: dict[str, float] = {}
    model_type_counts: dict[str, int] = {}
    route_wins: dict[str, int] = {}

    success_total = 0
    resonance_total = 0.0
    path_quality_total = 0.0
    network_improvement_total = 0.0
    merit_total = 0.0

    receiver_resonance_trend: list[dict[str, Any]] = []
    path_quality_trend: list[dict[str, Any]] = []
    network_improvement_trend: list[dict[str, Any]] = []
    quality_score_trend: list[dict[str, Any]] = []
    average_merit_trend: list[dict[str, Any]] = []
    cycles: list[dict[str, Any]] = []

    sorted_ledgers = sorted(ledgers, key=lambda item: str(item.get("timestamp", "")))
    for index, ledger_dict in enumerate(sorted_ledgers, start=1):
        ledger = _as_namespace(ledger_dict)
        timestamp = str(getattr(ledger, "timestamp", ""))
        outcome = getattr(ledger, "outcome", None)
        attribution = getattr(ledger, "attribution", None)
        final_decision = getattr(ledger, "final_decision", None)
        participants = list(getattr(ledger, "participants", []) or [])

        best_model = str(getattr(attribution, "best_contributor_model_id", "") or "unknown")
        best_contributor_counts[best_model] = best_contributor_counts.get(best_model, 0) + 1
        route_key = str(getattr(final_decision, "selected_route", "") or "unknown")
        route_wins[route_key] = route_wins.get(route_key, 0) + 1

        contribution_breakdown = list(getattr(attribution, "contribution_breakdown", []) or [])
        for entry in contribution_breakdown:
            model_id = str(getattr(entry, "model_id", "") or "unknown")
            contribution_score = float(getattr(entry, "total_contribution_score", 0.0) or 0.0)
            cumulative_contribution_scores[model_id] = cumulative_contribution_scores.get(model_id, 0.0) + contribution_score

        by_model = {
            str(getattr(entry, "model_id", "") or ""): float(getattr(entry, "total_contribution_score", 0.0) or 0.0)
            for entry in contribution_breakdown
        }
        for participant in participants:
            model_type = str(getattr(participant, "model_type", "") or "unknown")
            model_id = str(getattr(participant, "model_id", "") or "")
            contribution_score = by_model.get(model_id, 0.0)
            model_type_totals[model_type] = model_type_totals.get(model_type, 0.0) + contribution_score
            model_type_counts[model_type] = model_type_counts.get(model_type, 0) + 1

        success_value = 1 if bool(getattr(outcome, "success", False)) else 0
        resonance_value = float(getattr(outcome, "receiver_resonance_score", 0.0) or 0.0)
        path_quality_value = float(getattr(outcome, "path_quality", 0.0) or 0.0)
        network_improvement_value = float(getattr(outcome, "network_improvement", 0.0) or 0.0)
        quality_score_value = quality_score_from_council_outcome(outcome)

        merit_updates = build_merit_updates_from_council_ledger(
            ledger,
            quality_score=quality_score_value,
            total_tasks_last_24h=max(len(participants), 1),
        )
        average_merit_value = (
            sum(float(update.get("merit_score", 0.0) or 0.0) for update in merit_updates) / len(merit_updates)
            if merit_updates
            else 0.0
        )

        success_total += success_value
        resonance_total += resonance_value
        path_quality_total += path_quality_value
        network_improvement_total += network_improvement_value
        merit_total += average_merit_value

        point = {
            "index": index,
            "cycle_id": str(getattr(ledger, "cycle_id", "")),
            "task_id": str(getattr(ledger, "task_id", "")),
            "timestamp": timestamp,
            "label": str(getattr(ledger, "cycle_id", "")) or f"cycle-{index}",
        }
        receiver_resonance_trend.append({**point, "value": _round(resonance_value)})
        path_quality_trend.append({**point, "value": _round(path_quality_value)})
        network_improvement_trend.append({**point, "value": _round(network_improvement_value)})
        quality_score_trend.append({**point, "value": _round(quality_score_value)})
        average_merit_trend.append({**point, "value": _round(average_merit_value)})

        cycles.append(
            {
                **point,
                "best_contributor_model_id": best_model,
                "selected_route": route_key,
                "success": bool(success_value),
                "receiver_resonance_score": _round(resonance_value),
                "path_quality": _round(path_quality_value),
                "network_improvement": _round(network_improvement_value),
                "quality_score": _round(quality_score_value),
                "average_merit_score": _round(average_merit_value),
            }
        )

    def histogram(mapping: dict[str, float | int]) -> list[dict[str, Any]]:
        return [
            {"label": label, "value": _round(value)}
            for label, value in sorted(mapping.items(), key=lambda item: (-float(item[1]), item[0]))
        ]

    model_type_average_contribution = {
        label: (model_type_totals[label] / model_type_counts[label])
        for label in model_type_totals
        if model_type_counts.get(label)
    }

    top_best_contributor_model_id = max(
        best_contributor_counts.items(),
        key=lambda item: (item[1], item[0]),
    )[0]

    ledger_count = len(sorted_ledgers)
    return {
        "ledger_count": ledger_count,
        "summary": {
            "success_rate": _round(success_total / ledger_count),
            "average_receiver_resonance": _round(resonance_total / ledger_count),
            "average_path_quality": _round(path_quality_total / ledger_count),
            "average_network_improvement": _round(network_improvement_total / ledger_count),
            "average_merit_score": _round(merit_total / ledger_count),
            "top_best_contributor_model_id": top_best_contributor_model_id,
        },
        "histograms": {
            "best_contributor_counts": histogram(best_contributor_counts),
            "cumulative_contribution_scores": histogram(cumulative_contribution_scores),
            "model_type_average_contribution": histogram(model_type_average_contribution),
            "route_wins": histogram(route_wins),
        },
        "trends": {
            "receiver_resonance": receiver_resonance_trend,
            "path_quality": path_quality_trend,
            "network_improvement": network_improvement_trend,
            "quality_score": quality_score_trend,
            "average_merit_score": average_merit_trend,
        },
        "cycles": cycles,
    }
