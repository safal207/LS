# -*- coding: utf-8 -*-
"""Alignment strategy playbook MVP — compact operational conversation plan.

Builds one structured playbook object from current strategy recommendations
and alignment context. Advisory/read-only layer: never mutates upstream state,
routing decisions, or recommendations.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


_PHASE_ORDER = [
    "acknowledge_tension",
    "separate_cause_vs_behavior",
    "synchronize_positions",
    "co_create_solution",
]


def _action_to_phase(action: str) -> str | None:
    a = (action or "").lower()
    if any(k in a for k in ("acknowledge", "shared concern", "name the")):
        return "acknowledge_tension"
    if any(k in a for k in ("background", "visible behavior", "separate")):
        return "separate_cause_vs_behavior"
    if any(k in a for k in ("synchronize", "shared goal", "avoid winner/loser")):
        return "synchronize_positions"
    if any(k in a for k in ("shared options", "invite", "co-ownership", "proposing")):
        return "co_create_solution"
    return None


def _build_playbook_steps(recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    phase_actions: dict[str, list[str]] = {k: [] for k in _PHASE_ORDER}
    for rec in recommendations:
        for action in (rec.get("recommended_actions") or []):
            phase = _action_to_phase(str(action))
            if not phase:
                continue
            if action not in phase_actions[phase]:
                phase_actions[phase].append(str(action))

    steps: list[dict[str, Any]] = []
    for phase in _PHASE_ORDER:
        actions = phase_actions[phase]
        if actions:
            steps.append({"phase": phase, "actions": actions[:3]})

    if not steps and recommendations:
        fallback = recommendations[0].get("recommended_actions") or []
        steps.append({"phase": "co_create_solution", "actions": [str(a) for a in fallback[:3]]})
    return steps


def build_alignment_strategy_playbook(
    recommendations: list[dict[str, Any]],
    *,
    alignment_report: dict[str, Any] | None = None,
    calibration_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the current strategy playbook object for this cycle."""
    if not recommendations:
        return {
            "current_playbook_id": "",
            "selected_strategy_ids": [],
            "why_selected": "no qualifying strategies available for current context",
            "confidence": 0.0,
            "risk_notes": ["insufficient strategy evidence for a structured playbook"],
            "steps": [],
        }

    selected_ids = [str(r.get("strategy_id") or "") for r in recommendations if r.get("strategy_id")]
    selected_ids = selected_ids[:3]
    steps = _build_playbook_steps(recommendations[:3])

    eff_rates = [float(r.get("effective_rate") or 0.0) for r in recommendations[:3]]
    support = [int(r.get("support_count") or 0) for r in recommendations[:3]]
    base_conf = (sum(eff_rates) / max(len(eff_rates), 1)) * 0.7 + min(sum(support), 15) / 15 * 0.3
    confidence = round(min(max(base_conf, 0.0), 1.0), 4)

    report = alignment_report or {}
    hotspots = report.get("pairwise_hotspots") or []
    hotspot_name = ""
    if hotspots and isinstance(hotspots[0], dict):
        hotspot_name = str(hotspots[0].get("tension_axis") or "")

    why_selected = "selected from recurrent effective patterns"
    if hotspot_name:
        why_selected = f"selected for current tension axis: {hotspot_name}"

    risk_notes: list[str] = []
    if confidence < 0.45:
        risk_notes.append("low confidence: limited support or mixed effectiveness")
    if calibration_summary:
        # Support both flat structure (our calibration module) and {"overview": {...}}
        overview = calibration_summary.get("overview") or calibration_summary
        if int(overview.get("recommended_but_not_adopted_total") or 0) > 0:
            risk_notes.append("adoption gap detected: recommendations often not adopted")
        if int(overview.get("adopted_but_low_outcome_total") or 0) > 0:
            risk_notes.append("outcome risk: some adopted strategies had low outcome quality")
    if hotspot_name:
        risk_notes.append(f"monitor escalation risk on axis: {hotspot_name}")
    if not risk_notes:
        risk_notes.append("no critical risk notes in current cycle")

    playbook_id = hashlib.sha1(
        ("|".join(selected_ids) + "|" + hotspot_name).encode()
    ).hexdigest()[:12]

    return {
        "current_playbook_id": playbook_id,
        "selected_strategy_ids": selected_ids,
        "why_selected": why_selected,
        "confidence": confidence,
        "risk_notes": risk_notes[:4],
        "steps": steps,
    }


@dataclass
class AlignmentStrategyPlaybookMetrics:
    calls_total: int = 0
    empty_total: int = 0
    nonempty_total: int = 0
    strategies_selected_total: int = 0

    def to_dict(self) -> dict[str, Any]:
        avg = round(self.strategies_selected_total / self.nonempty_total, 3) if self.nonempty_total else 0.0
        return {
            "calls_total": self.calls_total,
            "empty_total": self.empty_total,
            "nonempty_total": self.nonempty_total,
            "strategies_selected_total": self.strategies_selected_total,
            "avg_selected_per_nonempty": avg,
        }
