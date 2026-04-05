# -*- coding: utf-8 -*-
"""Collective Coordination Snapshot MVP - top-level scene snapshot layer.

Builds a compact, deterministic, read-only snapshot by aggregating already-existing
structured layers:
- multi_party_alignment_state
- bridge_graph_state
- bridge_stabilization_order

This module is advisory/observability only:
- Never mutates inputs.
- Never changes routing / graph / backend / reuse logic.
- Never injects prompts or recommendations.
- No LLM, no external dependencies, no persistence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_MAX_TOP_BRIDGES = 3
_MAX_TOP_STABILIZATION = 3
_MAX_TOP_RISK_PARTIES = 3
_MAX_REASON_CHARS = 140


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


@dataclass
class CollectiveCoordinationSnapshot:
    coordination_state_label: str = "coherent"
    coordination_risk: float = 0.0
    primary_fracture_line: dict[str, Any] | None = None
    dominant_tension_axis: str = "unknown"
    dominant_bridge_type: str = "unknown"
    dominant_stabilization_mode: str = "unknown"
    group_fragmentation_level: str = "low"
    alignment_convergence: float = 0.0
    adoption_coverage: float = 0.0
    top_bridge_candidates: list[dict[str, Any]] = field(default_factory=list)
    top_stabilization_edges: list[dict[str, Any]] = field(default_factory=list)
    top_risk_parties: list[dict[str, Any]] = field(default_factory=list)
    summary_reason: str = "no coordination signals available"
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "coordination_state_label": self.coordination_state_label,
            "coordination_risk": round(_clamp01(self.coordination_risk), 4),
            "primary_fracture_line": self.primary_fracture_line,
            "dominant_tension_axis": self.dominant_tension_axis,
            "dominant_bridge_type": self.dominant_bridge_type,
            "dominant_stabilization_mode": self.dominant_stabilization_mode,
            "group_fragmentation_level": self.group_fragmentation_level,
            "alignment_convergence": round(_clamp01(self.alignment_convergence), 4),
            "adoption_coverage": round(_clamp01(self.adoption_coverage), 4),
            "top_bridge_candidates": self.top_bridge_candidates,
            "top_stabilization_edges": self.top_stabilization_edges,
            "top_risk_parties": self.top_risk_parties,
            "summary_reason": self.summary_reason,
            "confidence": round(_clamp01(self.confidence), 4),
        }


@dataclass
class CollectiveCoordinationMetrics:
    calls_total: int = 0
    snapshots_total: int = 0
    empty_inputs_total: int = 0
    high_risk_total: int = 0
    medium_risk_total: int = 0
    low_risk_total: int = 0
    coherent_total: int = 0
    strained_total: int = 0
    fragmented_total: int = 0
    unstable_total: int = 0
    escalating_total: int = 0
    converging_total: int = 0
    diverging_total: int = 0
    stable_total: int = 0
    nonempty_fracture_line_total: int = 0
    urgent_stabilization_total: int = 0
    _coordination_risk_sum: float = 0.0

    @property
    def avg_coordination_risk(self) -> float:
        if self.snapshots_total <= 0:
            return 0.0
        return round(self._coordination_risk_sum / self.snapshots_total, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls_total": self.calls_total,
            "snapshots_total": self.snapshots_total,
            "empty_inputs_total": self.empty_inputs_total,
            "high_risk_total": self.high_risk_total,
            "medium_risk_total": self.medium_risk_total,
            "low_risk_total": self.low_risk_total,
            "coherent_total": self.coherent_total,
            "strained_total": self.strained_total,
            "fragmented_total": self.fragmented_total,
            "unstable_total": self.unstable_total,
            "escalating_total": self.escalating_total,
            "converging_total": self.converging_total,
            "diverging_total": self.diverging_total,
            "stable_total": self.stable_total,
            "nonempty_fracture_line_total": self.nonempty_fracture_line_total,
            "urgent_stabilization_total": self.urgent_stabilization_total,
            "avg_coordination_risk": self.avg_coordination_risk,
        }


def _fragmentation_to_score(level: str) -> float:
    if level == "high":
        return 1.0
    if level == "medium":
        return 0.55
    return 0.15


def _state_to_score(label: str) -> float:
    if label == "escalating":
        return 1.0
    if label == "diverging":
        return 0.75
    if label == "stable":
        return 0.4
    return 0.2


def _compute_coordination_risk(
    multi_party_state: dict[str, Any] | None,
    bridge_graph_state: dict[str, Any] | None,
    bridge_stabilization_order: dict[str, Any] | None,
) -> float:
    mp = multi_party_state if isinstance(multi_party_state, dict) else {}
    bg = bridge_graph_state if isinstance(bridge_graph_state, dict) else {}
    bo = bridge_stabilization_order if isinstance(bridge_stabilization_order, dict) else {}

    state_label = str(mp.get("state_label") or "stable")
    frag = str(bg.get("fragmentation_level") or "low")
    convergence = _clamp01(_safe_float(mp.get("alignment_convergence"), 0.0))
    adoption = _clamp01(_safe_float(mp.get("adoption_coverage"), 0.0))

    highest_edges = [e for e in (bg.get("highest_priority_edges") or []) if isinstance(e, dict)]
    top_edge_priority = max((_safe_float(e.get("bridge_priority"), 0.0) for e in highest_edges), default=0.0)

    urgent_edges = [e for e in (bo.get("urgent_edges") or []) if isinstance(e, dict)]
    ordered_edges = [e for e in (bo.get("ordered_edges") or []) if isinstance(e, dict)]
    urgent_ratio = (len(urgent_edges) / max(len(ordered_edges), 1)) if ordered_edges else 0.0

    risk = 0.0
    risk += 0.26 * _state_to_score(state_label)
    risk += 0.22 * _fragmentation_to_score(frag)
    risk += 0.20 * _clamp01(top_edge_priority)
    risk += 0.17 * _clamp01(urgent_ratio)
    risk += 0.10 * (1.0 - convergence)
    risk += 0.05 * (1.0 - adoption)

    return round(_clamp01(risk), 4)


def _label_coordination_state(
    *,
    coordination_risk: float,
    multi_party_state: dict[str, Any] | None,
    bridge_graph_state: dict[str, Any] | None,
    bridge_stabilization_order: dict[str, Any] | None,
) -> str:
    mp = multi_party_state if isinstance(multi_party_state, dict) else {}
    bg = bridge_graph_state if isinstance(bridge_graph_state, dict) else {}
    bo = bridge_stabilization_order if isinstance(bridge_stabilization_order, dict) else {}

    state_label = str(mp.get("state_label") or "stable")
    frag = str(bg.get("fragmentation_level") or "low")
    urgent_count = len([e for e in (bo.get("urgent_edges") or []) if isinstance(e, dict)])

    if state_label == "escalating" or urgent_count >= 2 or coordination_risk >= 0.85:
        return "escalating"
    if coordination_risk >= 0.70:
        return "unstable"
    if frag == "high" or coordination_risk >= 0.55:
        return "fragmented"
    if state_label in {"diverging", "stable"} or coordination_risk >= 0.35:
        return "strained"
    return "coherent"


def _build_primary_fracture_line(
    bridge_graph_state: dict[str, Any] | None,
    multi_party_state: dict[str, Any] | None,
) -> dict[str, Any] | None:
    bg = bridge_graph_state if isinstance(bridge_graph_state, dict) else {}
    mp = multi_party_state if isinstance(multi_party_state, dict) else {}

    top = [e for e in (bg.get("highest_priority_edges") or []) if isinstance(e, dict)]
    if not top:
        return None

    edge = top[0]
    reason = str(edge.get("bridge_reason") or "highest bridge priority")[:_MAX_REASON_CHARS]
    return {
        "from_party_id": str(edge.get("from_party_id") or ""),
        "to_party_id": str(edge.get("to_party_id") or ""),
        "bridge_type": str(edge.get("bridge_type") or "unknown"),
        "tension_axis": str(
            edge.get("tension_axis")
            or mp.get("dominant_tension_axis")
            or "unknown"
        ),
        "reason": reason,
    }


def _build_top_risk_parties(multi_party_state: dict[str, Any] | None) -> list[dict[str, Any]]:
    mp = multi_party_state if isinstance(multi_party_state, dict) else {}
    parties = [p for p in (mp.get("parties") or []) if isinstance(p, dict)]

    scored: list[tuple[float, dict[str, Any]]] = []
    for p in parties:
        pid = str(p.get("party_id") or "")
        label = str(p.get("position_label") or "neutral")
        gap = _clamp01(_safe_float(p.get("alignment_gap"), 0.0))
        hotspots = max(0, _safe_int(p.get("hotspot_count"), 0))

        label_bonus = 0.18 if label == "tension_source" else (0.08 if label == "responsive" else 0.0)
        hotspot_score = _clamp01(hotspots / 5.0)
        risk = _clamp01((gap * 0.62) + (hotspot_score * 0.28) + label_bonus)

        reason = (
            f"gap={gap:.2f}, hotspots={hotspots}, posture={label}"
        )[:_MAX_REASON_CHARS]
        scored.append((risk, {
            "party_id": pid,
            "position_label": label,
            "alignment_gap": round(gap, 4),
            "hotspot_count": hotspots,
            "reason": reason,
        }))

    scored.sort(key=lambda t: (-t[0], t[1]["party_id"]))
    return [entry for _, entry in scored[:_MAX_TOP_RISK_PARTIES]]


def _build_snapshot_reason(fields: dict[str, Any]) -> str:
    label = str(fields.get("coordination_state_label") or "coherent")
    frag = str(fields.get("group_fragmentation_level") or "low")
    urgent = _safe_int(fields.get("urgent_count"), 0)
    convergence = _clamp01(_safe_float(fields.get("alignment_convergence"), 0.0))

    if label == "escalating":
        return "urgent stabilization edges and elevated risk indicate escalating coordination"
    if label == "unstable":
        return "high fragmentation and high-priority bridges indicate unstable coordination"
    if label == "fragmented":
        return "multiple fracture signals and medium-high risk indicate fragmented coordination"
    if label == "strained":
        if frag in {"medium", "high"}:
            return "bridges exist, but fragmentation and tension keep coordination strained"
        return "convergence is partial, yet tension remains above coherent baseline"
    if convergence >= 0.7 and urgent == 0:
        return "coordination is coherent with low fragmentation and no urgent fracture lines"
    return "coordination remains coherent with manageable tension"


def build_collective_coordination_snapshot(
    multi_party_state: dict[str, Any] | None = None,
    bridge_graph_state: dict[str, Any] | None = None,
    bridge_stabilization_order: dict[str, Any] | None = None,
) -> CollectiveCoordinationSnapshot:
    """Build deterministic, bounded top-level coordination snapshot."""
    mp = multi_party_state if isinstance(multi_party_state, dict) else {}
    bg = bridge_graph_state if isinstance(bridge_graph_state, dict) else {}
    bo = bridge_stabilization_order if isinstance(bridge_stabilization_order, dict) else {}

    risk = _compute_coordination_risk(mp, bg, bo)

    highest = [e for e in (bg.get("highest_priority_edges") or []) if isinstance(e, dict)]
    top_bridges: list[dict[str, Any]] = []
    for edge in highest[:_MAX_TOP_BRIDGES]:
        top_bridges.append({
            "from_party_id": str(edge.get("from_party_id") or ""),
            "to_party_id": str(edge.get("to_party_id") or ""),
            "bridge_type": str(edge.get("bridge_type") or "unknown"),
            "bridge_priority": round(_clamp01(_safe_float(edge.get("bridge_priority"), 0.0)), 4),
            "bridge_strength": round(_clamp01(_safe_float(edge.get("bridge_strength"), 0.0)), 4),
        })

    ordered = [e for e in (bo.get("ordered_edges") or []) if isinstance(e, dict)]
    top_stabilization: list[dict[str, Any]] = []
    for edge in ordered[:_MAX_TOP_STABILIZATION]:
        top_stabilization.append({
            "rank": max(1, _safe_int(edge.get("rank"), len(top_stabilization) + 1)),
            "from_party_id": str(edge.get("from_party_id") or ""),
            "to_party_id": str(edge.get("to_party_id") or ""),
            "stabilization_label": str(edge.get("stabilization_label") or "monitor"),
            "recommended_timing": str(edge.get("recommended_timing") or "later"),
            "stabilization_score": round(_clamp01(_safe_float(edge.get("stabilization_score"), 0.0)), 4),
        })

    fracture = _build_primary_fracture_line(bg, mp)
    top_risk_parties = _build_top_risk_parties(mp)
    state_label = _label_coordination_state(
        coordination_risk=risk,
        multi_party_state=mp,
        bridge_graph_state=bg,
        bridge_stabilization_order=bo,
    )

    confidence_signals = 0
    confidence_signals += 1 if mp else 0
    confidence_signals += 1 if bg else 0
    confidence_signals += 1 if bo else 0
    confidence = round(confidence_signals / 3.0, 4)

    summary = _build_snapshot_reason({
        "coordination_state_label": state_label,
        "group_fragmentation_level": str(bg.get("fragmentation_level") or "low"),
        "alignment_convergence": _clamp01(_safe_float(mp.get("alignment_convergence"), 0.0)),
        "urgent_count": len([e for e in (bo.get("urgent_edges") or []) if isinstance(e, dict)]),
    })

    return CollectiveCoordinationSnapshot(
        coordination_state_label=state_label,
        coordination_risk=risk,
        primary_fracture_line=fracture,
        dominant_tension_axis=str(mp.get("dominant_tension_axis") or "unknown"),
        dominant_bridge_type=str(bg.get("dominant_bridge_type") or "unknown"),
        dominant_stabilization_mode=str(bo.get("dominant_stabilization_mode") or "unknown"),
        group_fragmentation_level=str(bg.get("fragmentation_level") or "low"),
        alignment_convergence=_clamp01(_safe_float(mp.get("alignment_convergence"), 0.0)),
        adoption_coverage=_clamp01(_safe_float(mp.get("adoption_coverage"), 0.0)),
        top_bridge_candidates=top_bridges,
        top_stabilization_edges=top_stabilization,
        top_risk_parties=top_risk_parties,
        summary_reason=summary[:_MAX_REASON_CHARS],
        confidence=confidence,
    )
