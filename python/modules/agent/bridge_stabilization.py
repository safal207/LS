# -*- coding: utf-8 -*-
"""Bridge Stabilization Order MVP — advisory ordering layer over bridge graph.

Builds a compact, deterministic stabilization order from the already-computed
bridge_graph_state (optionally informed by multi_party_alignment_state).

Advisory only:
- Never mutates bridge_graph_state or multi_party_alignment_state.
- Never changes routing / graph_mode / backend / reuse logic.
- Never injects into prompts.
- Never modifies playbook/recommender/feedback logic.
- No LLM, no embeddings, no persistence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_MAX_ORDERED_EDGES = 10
_MAX_URGENT_EDGES = 3
_MAX_QUICK_WIN_EDGES = 3
_MAX_DEFER_EDGES = 3
_MAX_REASON_CHARS = 120

_LABEL_URGENT = "urgent_stabilize"
_LABEL_EARLY = "early_stabilize"
_LABEL_QUICK_WIN = "quick_win"
_LABEL_MONITOR = "monitor"
_LABEL_DEFER = "defer"

_TIMING_BY_LABEL = {
    _LABEL_URGENT: "now",
    _LABEL_EARLY: "soon",
    _LABEL_QUICK_WIN: "soon",
    _LABEL_MONITOR: "later",
    _LABEL_DEFER: "later",
}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


@dataclass
class BridgeStabilizationEntry:
    rank: int
    from_party_id: str
    to_party_id: str
    bridge_type: str
    bridge_priority: float
    bridge_strength: float
    stabilization_score: float
    stabilization_label: str
    stabilization_reason: str
    recommended_timing: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": int(self.rank),
            "from_party_id": self.from_party_id,
            "to_party_id": self.to_party_id,
            "bridge_type": self.bridge_type,
            "bridge_priority": round(_clamp01(self.bridge_priority), 4),
            "bridge_strength": round(_clamp01(self.bridge_strength), 4),
            "stabilization_score": round(_clamp01(self.stabilization_score), 4),
            "stabilization_label": self.stabilization_label,
            "stabilization_reason": self.stabilization_reason,
            "recommended_timing": self.recommended_timing,
            "confidence": round(_clamp01(self.confidence), 4),
        }


@dataclass
class BridgeStabilizationOrder:
    ordered_edges: list[dict[str, Any]] = field(default_factory=list)
    urgent_edges: list[dict[str, Any]] = field(default_factory=list)
    early_stabilization_edges: list[dict[str, Any]] = field(default_factory=list)
    quick_win_edges: list[dict[str, Any]] = field(default_factory=list)
    defer_edges: list[dict[str, Any]] = field(default_factory=list)
    dominant_stabilization_mode: str = "observe_and_stage"
    summary_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordered_edges": self.ordered_edges,
            "urgent_edges": self.urgent_edges,
            "early_stabilization_edges": self.early_stabilization_edges,
            "quick_win_edges": self.quick_win_edges,
            "defer_edges": self.defer_edges,
            "dominant_stabilization_mode": self.dominant_stabilization_mode,
            "summary_reason": self.summary_reason,
        }


@dataclass
class BridgeStabilizationMetrics:
    calls_total: int = 0
    orders_total: int = 0
    edges_processed_total: int = 0
    urgent_stabilize_total: int = 0
    early_stabilize_total: int = 0
    quick_win_total: int = 0
    monitor_total: int = 0
    defer_total: int = 0
    _stabilization_score_sum: float = 0.0
    crisis_first_total: int = 0
    high_priority_first_total: int = 0
    quick_wins_first_total: int = 0
    observe_and_stage_total: int = 0
    empty_inputs_total: int = 0

    @property
    def avg_stabilization_score(self) -> float:
        if self.edges_processed_total <= 0:
            return 0.0
        return round(self._stabilization_score_sum / self.edges_processed_total, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls_total": self.calls_total,
            "orders_total": self.orders_total,
            "edges_processed_total": self.edges_processed_total,
            "urgent_stabilize_total": self.urgent_stabilize_total,
            "early_stabilize_total": self.early_stabilize_total,
            "quick_win_total": self.quick_win_total,
            "monitor_total": self.monitor_total,
            "defer_total": self.defer_total,
            "avg_stabilization_score": self.avg_stabilization_score,
            "crisis_first_total": self.crisis_first_total,
            "high_priority_first_total": self.high_priority_first_total,
            "quick_wins_first_total": self.quick_wins_first_total,
            "observe_and_stage_total": self.observe_and_stage_total,
            "empty_inputs_total": self.empty_inputs_total,
        }


def _extract_group_state(bridge_graph_state: dict[str, Any], multi_party_state: dict[str, Any] | None) -> str:
    if isinstance(multi_party_state, dict):
        label = str(multi_party_state.get("state_label") or "").strip()
        if label:
            return label
    reason = str((bridge_graph_state or {}).get("summary_reason") or "")
    if "state:" in reason:
        return reason.split("state:", 1)[1].strip().split(";", 1)[0].strip()
    return "stable"


def _extract_fragmentation(bridge_graph_state: dict[str, Any]) -> str:
    return str((bridge_graph_state or {}).get("fragmentation_level") or "low").strip() or "low"


def _label_stabilization_entry(edge: dict[str, Any], group_state: str | None = None, fragmentation_level: str | None = None) -> str:
    priority = _clamp01(_safe_float(edge.get("bridge_priority"), 0.0))
    strength = _clamp01(_safe_float(edge.get("bridge_strength"), 0.0))
    bridge_type = str(edge.get("bridge_type") or "")
    gs = str(group_state or "stable")
    frag = str(fragmentation_level or "low")

    if priority >= 0.80 and (gs == "escalating" or bridge_type == "stabilization_bridge" or frag == "high"):
        return _LABEL_URGENT
    if priority >= 0.64:
        return _LABEL_EARLY
    if strength >= 0.70 and priority <= 0.70 and gs != "escalating":
        return _LABEL_QUICK_WIN
    if priority >= 0.35 or strength >= 0.45:
        return _LABEL_MONITOR
    return _LABEL_DEFER


def _compute_stabilization_score(edge: dict[str, Any], group_state: str | None = None) -> float:
    priority = _clamp01(_safe_float(edge.get("bridge_priority"), 0.0))
    strength = _clamp01(_safe_float(edge.get("bridge_strength"), 0.0))
    confidence = _clamp01(_safe_float(edge.get("confidence"), 0.0))
    gs = str(group_state or "stable")

    score = (priority * 0.62) + (strength * 0.26) + (confidence * 0.07)
    if gs == "escalating":
        score += 0.08
    elif gs == "diverging":
        score += 0.04
    elif gs == "converging":
        score -= 0.03

    return round(_clamp01(score), 4)


def _build_stabilization_reason(edge: dict[str, Any], label: str, group_state: str | None = None) -> str:
    priority = _clamp01(_safe_float(edge.get("bridge_priority"), 0.0))
    strength = _clamp01(_safe_float(edge.get("bridge_strength"), 0.0))
    bridge_type = str(edge.get("bridge_type") or "")
    gs = str(group_state or "stable")

    reason = (
        f"{label}: priority={priority:.2f}, strength={strength:.2f}, "
        f"type={bridge_type or 'unknown'}, state={gs}"
    )
    return reason[:_MAX_REASON_CHARS]


def _dominant_mode_from_labels(labels: list[str], group_state: str | None = None) -> str:
    counts = {
        _LABEL_URGENT: labels.count(_LABEL_URGENT),
        _LABEL_EARLY: labels.count(_LABEL_EARLY),
        _LABEL_QUICK_WIN: labels.count(_LABEL_QUICK_WIN),
        _LABEL_MONITOR: labels.count(_LABEL_MONITOR),
        _LABEL_DEFER: labels.count(_LABEL_DEFER),
    }
    gs = str(group_state or "stable")

    if counts[_LABEL_URGENT] > 0 and (gs == "escalating" or counts[_LABEL_URGENT] >= counts[_LABEL_EARLY]):
        return "crisis_first"
    if counts[_LABEL_EARLY] >= max(counts[_LABEL_QUICK_WIN], counts[_LABEL_MONITOR], counts[_LABEL_DEFER]) and counts[_LABEL_EARLY] > 0:
        return "high_priority_first"
    if counts[_LABEL_QUICK_WIN] > 0 and counts[_LABEL_QUICK_WIN] >= counts[_LABEL_EARLY]:
        return "quick_wins_first"
    return "observe_and_stage"


def _summary_reason(mode: str, labels: list[str], total_edges: int) -> str:
    return (
        f"mode={mode}; total_edges={total_edges}; urgent={labels.count(_LABEL_URGENT)}; "
        f"early={labels.count(_LABEL_EARLY)}; quick={labels.count(_LABEL_QUICK_WIN)}; "
        f"defer={labels.count(_LABEL_DEFER)}"
    )


def build_bridge_stabilization_order(
    bridge_graph_state: dict[str, Any],
    multi_party_state: dict[str, Any] | None = None,
) -> BridgeStabilizationOrder:
    """Build deterministic, bounded advisory stabilization ordering over bridge edges."""
    if not isinstance(bridge_graph_state, dict):
        return BridgeStabilizationOrder(summary_reason="no bridge_graph_state provided")

    edges = [e for e in (bridge_graph_state.get("edges") or []) if isinstance(e, dict)]
    if not edges:
        return BridgeStabilizationOrder(summary_reason="no bridge edges available")

    group_state = _extract_group_state(bridge_graph_state, multi_party_state)
    fragmentation = _extract_fragmentation(bridge_graph_state)

    entries: list[BridgeStabilizationEntry] = []
    for edge in edges[:_MAX_ORDERED_EDGES]:
        label = _label_stabilization_entry(edge, group_state, fragmentation)
        score = _compute_stabilization_score(edge, group_state)
        entry = BridgeStabilizationEntry(
            rank=0,
            from_party_id=str(edge.get("from_party_id") or ""),
            to_party_id=str(edge.get("to_party_id") or ""),
            bridge_type=str(edge.get("bridge_type") or ""),
            bridge_priority=_clamp01(_safe_float(edge.get("bridge_priority"), 0.0)),
            bridge_strength=_clamp01(_safe_float(edge.get("bridge_strength"), 0.0)),
            stabilization_score=score,
            stabilization_label=label,
            stabilization_reason=_build_stabilization_reason(edge, label, group_state),
            recommended_timing=_TIMING_BY_LABEL.get(label, "later"),
            confidence=_clamp01(_safe_float(edge.get("confidence"), 0.0)),
        )
        entries.append(entry)

    entries.sort(
        key=lambda e: (
            -e.stabilization_score,
            -e.bridge_priority,
            -e.bridge_strength,
            e.from_party_id,
            e.to_party_id,
            e.bridge_type,
        )
    )

    for idx, entry in enumerate(entries, start=1):
        entry.rank = idx

    ordered = [e.to_dict() for e in entries[:_MAX_ORDERED_EDGES]]
    labels = [e.stabilization_label for e in entries]

    urgent = [d for d in ordered if d.get("stabilization_label") == _LABEL_URGENT][:_MAX_URGENT_EDGES]
    early = [d for d in ordered if d.get("stabilization_label") == _LABEL_EARLY]
    quick = [d for d in ordered if d.get("stabilization_label") == _LABEL_QUICK_WIN][:_MAX_QUICK_WIN_EDGES]
    defer = [d for d in ordered if d.get("stabilization_label") == _LABEL_DEFER][:_MAX_DEFER_EDGES]

    mode = _dominant_mode_from_labels(labels, group_state)
    summary = _summary_reason(mode, labels, len(ordered))

    return BridgeStabilizationOrder(
        ordered_edges=ordered,
        urgent_edges=urgent,
        early_stabilization_edges=early,
        quick_win_edges=quick,
        defer_edges=defer,
        dominant_stabilization_mode=mode,
        summary_reason=summary,
    )
