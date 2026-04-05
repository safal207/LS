# -*- coding: utf-8 -*-
"""Coordination Advisory Summary MVP.

Builds a compact deterministic summary layer over:
- collective_coordination_snapshot
- bridge_stabilization_order
- bridge_playbook_advisory

Advisory-only:
- Never mutates inputs.
- Never modifies routing/control logic.
- No LLM, no embeddings, no external dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_MAX_REASON_CHARS = 140

_ALLOWED_LABELS = {"ready", "fragile", "blocked", "insufficient_context"}
_ALLOWED_MODES = {
    "stabilization_first",
    "translation_first",
    "reframe_first",
    "pacing_first",
    "acknowledge_first",
    "mixed",
    "unknown",
}
_ALLOWED_SUPPORT = {"high", "medium", "low", "none", "unknown"}
_ALLOWED_RISK = {
    "coordination_risk",
    "fragmentation_pressure",
    "playbook_misalignment",
    "weak_bridge_support",
    "insufficient_context",
    "unknown",
}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _first_ordered_edge(bridge_stabilization_order: dict[str, Any] | None) -> dict[str, Any] | None:
    bo = bridge_stabilization_order if isinstance(bridge_stabilization_order, dict) else {}
    ordered = [e for e in (bo.get("ordered_edges") or []) if isinstance(e, dict)]
    return ordered[0] if ordered else None


def _stabilization_support(bridge_stabilization_order: dict[str, Any] | None) -> float:
    first = _first_ordered_edge(bridge_stabilization_order)
    if not first:
        return 0.0
    score = _clamp01(_safe_float(first.get("stabilization_score"), 0.0))
    if score >= 0.75:
        return 1.0
    if score >= 0.45:
        return 0.6
    return 0.3


def _derive_playbook_support_level(bridge_playbook_advisory: dict[str, Any] | None) -> str:
    pa = bridge_playbook_advisory if isinstance(bridge_playbook_advisory, dict) else {}
    label = _norm(pa.get("playbook_alignment_label"))

    by_label = {
        "well_aligned": "high",
        "partially_aligned": "medium",
        "weakly_aligned": "low",
        "misaligned": "none",
        "insufficient_context": "unknown",
    }
    mapped = by_label.get(label)
    if mapped:
        return mapped

    score = _clamp01(_safe_float(pa.get("playbook_alignment_score"), 0.0))
    if score >= 0.70:
        return "high"
    if score >= 0.45:
        return "medium"
    if score > 0.0:
        return "low"
    return "unknown"


def _derive_primary_mode(
    collective_coordination_snapshot: dict[str, Any] | None,
    bridge_stabilization_order: dict[str, Any] | None,
    bridge_playbook_advisory: dict[str, Any] | None,
) -> str:
    first = _first_ordered_edge(bridge_stabilization_order) or {}
    stabilization_label = _norm(first.get("stabilization_label"))
    if any(tok in stabilization_label for tok in ("urgent", "stabilize", "deescal")):
        return "stabilization_first"
    if "translate" in stabilization_label:
        return "translation_first"
    if "reframe" in stabilization_label:
        return "reframe_first"
    if any(tok in stabilization_label for tok in ("pace", "slow")):
        return "pacing_first"
    if any(tok in stabilization_label for tok in ("ack", "recogn")):
        return "acknowledge_first"

    pa = bridge_playbook_advisory if isinstance(bridge_playbook_advisory, dict) else {}
    fit = _norm(pa.get("dominant_bridge_playbook_fit"))
    fit_map = {
        "stabilization-led": "stabilization_first",
        "translation-led": "translation_first",
        "reframing-led": "reframe_first",
        "pacing-led": "pacing_first",
        "acknowledgment-led": "acknowledge_first",
        "mixed": "mixed",
    }
    if fit in fit_map:
        return fit_map[fit]

    cs = collective_coordination_snapshot if isinstance(collective_coordination_snapshot, dict) else {}
    bridge_type = _norm(cs.get("dominant_bridge_type"))
    bridge_map = {
        "stabilization_bridge": "stabilization_first",
        "translation_bridge": "translation_first",
        "reframing_bridge": "reframe_first",
        "pacing_bridge": "pacing_first",
        "acknowledgment_bridge": "acknowledge_first",
    }
    return bridge_map.get(bridge_type, "unknown")


def _is_effectively_empty(value: dict[str, Any] | None) -> bool:
    if not isinstance(value, dict) or not value:
        return True
    meaningful = [k for k, v in value.items() if k != "summary_reason" and v not in (None, "", [], {}, 0, 0.0)]
    return len(meaningful) == 0


def _derive_top_risk_driver(
    *,
    insufficient: bool,
    coordination_risk: float,
    support_level: str,
    alignment_label: str,
    dominant_fit: str,
    stabilization_support: float,
    collective_coordination_snapshot: dict[str, Any] | None,
) -> str:
    if insufficient:
        return "insufficient_context"
    if alignment_label == "misaligned":
        return "playbook_misalignment"
    if coordination_risk >= 0.75:
        return "coordination_risk"
    if support_level in {"low", "none"} and (dominant_fit in {"unknown", "mixed", ""} or stabilization_support <= 0.0):
        return "weak_bridge_support"

    cs = collective_coordination_snapshot if isinstance(collective_coordination_snapshot, dict) else {}
    frag = _norm(cs.get("group_fragmentation_level"))
    state = _norm(cs.get("coordination_state_label"))
    if frag in {"high", "medium"} or state in {"fragmented", "escalating", "diverging", "unstable"}:
        return "fragmentation_pressure"
    return "unknown"


def _build_summary_reason(
    *,
    label: str,
    support_level: str,
    stabilization_support: float,
    coordination_risk: float,
    top_risk_driver: str,
) -> str:
    if label == "insufficient_context":
        return "insufficient coordination context for reliable advisory summary"
    if label == "ready":
        reason = "scene is ready: playbook support is {} and stabilization path is clear".format(support_level)
    elif label == "blocked":
        if top_risk_driver == "playbook_misalignment":
            reason = "scene is blocked by playbook misalignment under high coordination pressure"
        else:
            reason = "scene is blocked: coordination pressure is high and support is too weak"
    else:
        reason = "scene is fragile: coordination risk is elevated and playbook grounding is limited"

    if stabilization_support <= 0.0 and label != "ready":
        reason = f"{reason}; stabilization support is minimal"
    if coordination_risk >= 0.85 and label != "ready":
        reason = f"{reason}; pressure remains high"

    reason = " ".join(reason.splitlines()).strip()
    if not reason:
        reason = "coordination advisory summary generated"
    return reason[:_MAX_REASON_CHARS]


@dataclass
class CoordinationAdvisorySummary:
    coordination_advisory_label: str = "insufficient_context"
    coordination_readiness: float = 0.0
    primary_intervention_mode: str = "unknown"
    playbook_support_level: str = "unknown"
    top_risk_driver: str = "insufficient_context"
    summary_reason: str = "insufficient coordination context for reliable advisory summary"

    def to_dict(self) -> dict[str, Any]:
        label = self.coordination_advisory_label if self.coordination_advisory_label in _ALLOWED_LABELS else "insufficient_context"
        mode = self.primary_intervention_mode if self.primary_intervention_mode in _ALLOWED_MODES else "unknown"
        support = self.playbook_support_level if self.playbook_support_level in _ALLOWED_SUPPORT else "unknown"
        risk = self.top_risk_driver if self.top_risk_driver in _ALLOWED_RISK else "unknown"
        reason = " ".join(str(self.summary_reason or "").splitlines()).strip()
        if not reason:
            reason = "insufficient coordination context for reliable advisory summary"

        return {
            "coordination_advisory_label": label,
            "coordination_readiness": round(_clamp01(self.coordination_readiness), 4),
            "primary_intervention_mode": mode,
            "playbook_support_level": support,
            "top_risk_driver": risk,
            "summary_reason": reason[:_MAX_REASON_CHARS],
        }


@dataclass
class CoordinationAdvisorySummaryMetrics:
    calls_total: int = 0
    summaries_total: int = 0
    ready_total: int = 0
    fragile_total: int = 0
    blocked_total: int = 0
    insufficient_context_total: int = 0
    stabilization_first_total: int = 0
    translation_first_total: int = 0
    reframe_first_total: int = 0
    pacing_first_total: int = 0
    acknowledge_first_total: int = 0
    mixed_total: int = 0
    _readiness_sum: float = 0.0

    @property
    def avg_coordination_readiness(self) -> float:
        if self.summaries_total <= 0:
            return 0.0
        return round(self._readiness_sum / self.summaries_total, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls_total": self.calls_total,
            "summaries_total": self.summaries_total,
            "ready_total": self.ready_total,
            "fragile_total": self.fragile_total,
            "blocked_total": self.blocked_total,
            "insufficient_context_total": self.insufficient_context_total,
            "stabilization_first_total": self.stabilization_first_total,
            "translation_first_total": self.translation_first_total,
            "reframe_first_total": self.reframe_first_total,
            "pacing_first_total": self.pacing_first_total,
            "acknowledge_first_total": self.acknowledge_first_total,
            "mixed_total": self.mixed_total,
            "avg_coordination_readiness": self.avg_coordination_readiness,
        }


def build_coordination_advisory_summary(
    collective_coordination_snapshot: dict[str, Any] | None = None,
    bridge_stabilization_order: dict[str, Any] | None = None,
    bridge_playbook_advisory: dict[str, Any] | None = None,
) -> CoordinationAdvisorySummary:
    """Build compact deterministic top-level coordination advisory summary."""
    cs = collective_coordination_snapshot if isinstance(collective_coordination_snapshot, dict) else {}
    bo = bridge_stabilization_order if isinstance(bridge_stabilization_order, dict) else {}
    pa = bridge_playbook_advisory if isinstance(bridge_playbook_advisory, dict) else {}

    insufficient = _is_effectively_empty(cs) and _is_effectively_empty(bo) and _is_effectively_empty(pa)
    if insufficient:
        return CoordinationAdvisorySummary()

    coordination_risk = _clamp01(_safe_float(cs.get("coordination_risk"), 1.0))
    playbook_alignment_score = _clamp01(_safe_float(pa.get("playbook_alignment_score"), 0.0))
    stabilization_support = _stabilization_support(bo)

    readiness = _clamp01(
        (0.45 * (1.0 - coordination_risk))
        + (0.35 * playbook_alignment_score)
        + (0.20 * stabilization_support)
    )

    support_level = _derive_playbook_support_level(pa)
    alignment_label = _norm(pa.get("playbook_alignment_label"))

    blocked = (
        (coordination_risk >= 0.80 and support_level in {"low", "none", "unknown"})
        or (alignment_label == "misaligned" and readiness < 0.45)
    )

    if readiness >= 0.68 and support_level in {"high", "medium"} and not blocked:
        advisory_label = "ready"
    elif blocked:
        advisory_label = "blocked"
    else:
        advisory_label = "fragile"

    mode = _derive_primary_mode(cs, bo, pa)
    top_risk = _derive_top_risk_driver(
        insufficient=False,
        coordination_risk=coordination_risk,
        support_level=support_level,
        alignment_label=alignment_label,
        dominant_fit=_norm(pa.get("dominant_bridge_playbook_fit")),
        stabilization_support=stabilization_support,
        collective_coordination_snapshot=cs,
    )
    reason = _build_summary_reason(
        label=advisory_label,
        support_level=support_level,
        stabilization_support=stabilization_support,
        coordination_risk=coordination_risk,
        top_risk_driver=top_risk,
    )

    return CoordinationAdvisorySummary(
        coordination_advisory_label=advisory_label,
        coordination_readiness=readiness,
        primary_intervention_mode=mode,
        playbook_support_level=support_level,
        top_risk_driver=top_risk,
        summary_reason=reason,
    )
