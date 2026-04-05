# -*- coding: utf-8 -*-
"""Bridge Graph MVP — structural relationship layer over multi-party alignment state.

Builds a read-only pairwise bridge graph from the already-computed
multi_party_alignment_state.  Identifies tension links, bridge candidates,
bridge types, and group-level fragmentation.

Advisory/structural layer only:
- Never modifies multi_party_state, alignment_report, routing, graph_mode,
  route_key, reuse/refine/full_run, or any upstream pipeline state.
- Never injects into prompts.
- Never changes playbook, recommender, feedback, or strategy logic.
- Pure functions. No LLM. No embeddings. No persistence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_PARTIES = 5
_MAX_EDGES = 10
_MAX_HIGHEST_PRIORITY = 3

# Bridge types (fixed, deterministic)
BRIDGE_TYPE_ACKNOWLEDGMENT = "acknowledgment_bridge"
BRIDGE_TYPE_PACING = "pacing_bridge"
BRIDGE_TYPE_REFRAMING = "reframing_bridge"
BRIDGE_TYPE_TRANSLATION = "translation_bridge"
BRIDGE_TYPE_STABILIZATION = "stabilization_bridge"

_ALL_BRIDGE_TYPES = (
    BRIDGE_TYPE_ACKNOWLEDGMENT,
    BRIDGE_TYPE_PACING,
    BRIDGE_TYPE_REFRAMING,
    BRIDGE_TYPE_TRANSLATION,
    BRIDGE_TYPE_STABILIZATION,
)

# Fragmentation thresholds
_HIGH_FRAGMENTATION_EDGE_DENSITY = 0.35   # below this density → high
_MEDIUM_FRAGMENTATION_EDGE_DENSITY = 0.65  # below this → medium; above → low

# Scoring helpers
_ESCALATING_PRIORITY_BOOST = 0.25
_DIVERGING_PRIORITY_BOOST = 0.15
_HIGH_GAP_THRESHOLD = 0.55
_HIGH_GAP_STRENGTH_BONUS = 0.20
_SHARED_AXIS_STRENGTH_BONUS = 0.15
_COMPLEMENTARY_STRENGTH_BONUS = 0.10


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class BridgeEdge:
    from_party_id: str
    to_party_id: str
    bridge_type: str
    tension_axis: str       # primary shared or dominant tension axis
    bridge_strength: float  # 0.0 .. 1.0 — how relevant/strong the connection need is
    bridge_priority: float  # 0.0 .. 1.0 — how urgent to stabilise this pair
    bridge_reason: str
    confidence: float       # 0.0 .. 1.0 — how much structural evidence supports this

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_party_id": self.from_party_id,
            "to_party_id": self.to_party_id,
            "bridge_type": self.bridge_type,
            "tension_axis": self.tension_axis,
            "bridge_strength": round(self.bridge_strength, 4),
            "bridge_priority": round(self.bridge_priority, 4),
            "bridge_reason": self.bridge_reason,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class BridgeGraphState:
    nodes: list[str] = field(default_factory=list)          # party IDs
    edges: list[dict[str, Any]] = field(default_factory=list)
    dominant_bridge_type: str = ""
    highest_priority_edges: list[dict[str, Any]] = field(default_factory=list)
    bridge_density: float = 0.0
    fragmentation_level: str = "low"    # "low" | "medium" | "high"
    summary_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "dominant_bridge_type": self.dominant_bridge_type,
            "highest_priority_edges": self.highest_priority_edges,
            "bridge_density": round(self.bridge_density, 4),
            "fragmentation_level": self.fragmentation_level,
            "summary_reason": self.summary_reason,
        }


# ---------------------------------------------------------------------------
# Internal: bridge type inference
# ---------------------------------------------------------------------------

_STABILIZATION_CUES = frozenset({
    "intent_conflict", "need_pressure_conflict", "why_mismatch",
})
_PACING_CUES = frozenset({
    "background_state_divergence", "need_pressure_conflict",
})
_REFRAMING_CUES = frozenset({
    "intent_conflict",
})
_TRANSLATION_CUES = frozenset({
    "why_mismatch",
})


def _infer_bridge_type(
    party_a: dict[str, Any],
    party_b: dict[str, Any],
    group_state: str,
) -> str:
    """Deterministic bridge type from structured party signals.

    Priority order (first match wins):
    1. stabilization_bridge — escalating group state OR both parties are tension_source
    2. reframing_bridge     — intent_conflict axis present on both sides
    3. pacing_bridge        — pacing/readiness axis (background_state_divergence or pressure conflict)
    4. translation_bridge   — why_mismatch axis (different internal models)
    5. acknowledgment_bridge — fallback: tension gap exists but no specific axis match
    """
    axes_a = set(str(x) for x in (party_a.get("tension_axes") or []))
    axes_b = set(str(x) for x in (party_b.get("tension_axes") or []))
    shared_axes = axes_a | axes_b  # union: either party contributes the axis

    label_a = str(party_a.get("position_label") or "neutral")
    label_b = str(party_b.get("position_label") or "neutral")

    # 1. stabilization: escalating group or both tension_source
    if group_state == "escalating" or (label_a == "tension_source" and label_b == "tension_source"):
        return BRIDGE_TYPE_STABILIZATION

    # 2. reframing: intent conflict axis is a "who is right" conflict
    if any("intent_conflict" in ax for ax in shared_axes):
        return BRIDGE_TYPE_REFRAMING

    # 3. pacing: background divergence or pressure conflict
    if any(
        ("background_state_divergence" in ax or "need_pressure_conflict" in ax)
        for ax in shared_axes
    ):
        return BRIDGE_TYPE_PACING

    # 4. translation: why_mismatch → different internal models
    if any("why_mismatch" in ax for ax in shared_axes):
        return BRIDGE_TYPE_TRANSLATION

    # 5. acknowledgment: fallback — gap exists but no specific type signal
    return BRIDGE_TYPE_ACKNOWLEDGMENT


# ---------------------------------------------------------------------------
# Internal: scoring
# ---------------------------------------------------------------------------

def _compute_bridge_strength(
    party_a: dict[str, Any],
    party_b: dict[str, Any],
) -> float:
    """Strength of the bridge need between two parties (0.0 .. 1.0).

    Higher when:
    - Both have high alignment_gap
    - They share a tension axis (real connection need)
    - One is a tension_source and the other is responsive (complementarity)
    """
    gap_a = float(party_a.get("alignment_gap") or 0.0)
    gap_b = float(party_b.get("alignment_gap") or 0.0)
    base = (gap_a + gap_b) / 2.0

    axes_a = set(str(x) for x in (party_a.get("tension_axes") or []))
    axes_b = set(str(x) for x in (party_b.get("tension_axes") or []))
    shared = axes_a & axes_b  # only axes both parties exhibit
    if shared:
        base += _SHARED_AXIS_STRENGTH_BONUS

    # High gap on either side
    if gap_a >= _HIGH_GAP_THRESHOLD or gap_b >= _HIGH_GAP_THRESHOLD:
        base += _HIGH_GAP_STRENGTH_BONUS

    label_a = str(party_a.get("position_label") or "neutral")
    label_b = str(party_b.get("position_label") or "neutral")
    complementary_pairs = {
        ("tension_source", "responsive"),
        ("responsive", "tension_source"),
        ("tension_source", "aligned"),
        ("aligned", "tension_source"),
    }
    if (label_a, label_b) in complementary_pairs:
        base += _COMPLEMENTARY_STRENGTH_BONUS

    return round(min(1.0, max(0.0, base)), 4)


def _compute_bridge_priority(
    party_a: dict[str, Any],
    party_b: dict[str, Any],
    group_state: str,
) -> float:
    """Priority of stabilising this bridge pair (0.0 .. 1.0).

    Higher when:
    - Group state is escalating or diverging
    - Either party is a tension_source
    - Both parties have high alignment_gap
    - Shared tension axes exist
    """
    gap_a = float(party_a.get("alignment_gap") or 0.0)
    gap_b = float(party_b.get("alignment_gap") or 0.0)
    base = (gap_a + gap_b) / 2.0

    label_a = str(party_a.get("position_label") or "neutral")
    label_b = str(party_b.get("position_label") or "neutral")

    if "tension_source" in (label_a, label_b):
        base += 0.15

    axes_a = set(str(x) for x in (party_a.get("tension_axes") or []))
    axes_b = set(str(x) for x in (party_b.get("tension_axes") or []))
    shared = axes_a & axes_b
    if shared:
        base += 0.10

    if group_state == "escalating":
        base += _ESCALATING_PRIORITY_BOOST
    elif group_state == "diverging":
        base += _DIVERGING_PRIORITY_BOOST

    return round(min(1.0, max(0.0, base)), 4)


def _primary_tension_axis(
    party_a: dict[str, Any],
    party_b: dict[str, Any],
    dominant: str,
) -> str:
    """Best shared or dominant axis for this edge, or empty string."""
    axes_a = set(str(x) for x in (party_a.get("tension_axes") or []))
    axes_b = set(str(x) for x in (party_b.get("tension_axes") or []))
    shared = sorted(axes_a & axes_b)
    if shared:
        return shared[0]
    union = sorted(axes_a | axes_b)
    if dominant and dominant in union:
        return dominant
    return union[0] if union else ""


def _bridge_reason(
    bridge_type: str,
    party_a: dict[str, Any],
    party_b: dict[str, Any],
    tension_axis: str,
) -> str:
    """Short, deterministic reason string."""
    a = party_a.get("party_id") or "party_a"
    b = party_b.get("party_id") or "party_b"
    label_a = party_a.get("position_label") or "neutral"
    label_b = party_b.get("position_label") or "neutral"

    if bridge_type == BRIDGE_TYPE_STABILIZATION:
        return f"{a}({label_a}) and {b}({label_b}) both under tension; de-escalation first"
    if bridge_type == BRIDGE_TYPE_REFRAMING:
        axis = tension_axis or "intent_conflict"
        return f"intent conflict ({axis}) between {a} and {b}; reframe as shared mismatch"
    if bridge_type == BRIDGE_TYPE_PACING:
        return f"readiness or pace mismatch between {a}({label_a}) and {b}({label_b})"
    if bridge_type == BRIDGE_TYPE_TRANSLATION:
        return f"different internal models between {a} and {b}; shared framing needed"
    # acknowledgment fallback
    gap_a = float(party_a.get("alignment_gap") or 0.0)
    gap_b = float(party_b.get("alignment_gap") or 0.0)
    return (
        f"tension gap between {a}(gap={gap_a:.2f}) and {b}(gap={gap_b:.2f}); "
        "acknowledge before pushing resolution"
    )


def _edge_confidence(
    party_a: dict[str, Any],
    party_b: dict[str, Any],
) -> float:
    """Confidence score: how much structural evidence supports this edge."""
    score = 0.0
    axes_a = party_a.get("tension_axes") or []
    axes_b = party_b.get("tension_axes") or []
    if axes_a or axes_b:
        score += 0.4
    if set(axes_a) & set(axes_b):
        score += 0.2
    hs_a = int(party_a.get("hotspot_count") or 0)
    hs_b = int(party_b.get("hotspot_count") or 0)
    if hs_a > 0 or hs_b > 0:
        score += 0.2
    label_a = str(party_a.get("position_label") or "neutral")
    label_b = str(party_b.get("position_label") or "neutral")
    if label_a != "neutral" or label_b != "neutral":
        score += 0.2
    return round(min(1.0, score), 4)


# ---------------------------------------------------------------------------
# Core builders
# ---------------------------------------------------------------------------

def build_bridge_edges(
    multi_party_state: dict[str, Any],
    alignment_report: dict[str, Any] | None = None,
) -> list[BridgeEdge]:
    """Build pairwise bridge edges from multi_party_alignment_state.

    Returns [] for fewer than 2 parties or invalid input.
    Never mutates its arguments. Never raises.
    """
    if not isinstance(multi_party_state, dict):
        return []

    parties: list[dict[str, Any]] = [
        p for p in (multi_party_state.get("parties") or [])
        if isinstance(p, dict)
    ]
    if len(parties) < 2:
        return []

    parties = parties[:_MAX_PARTIES]
    group_state = str(multi_party_state.get("state_label") or "stable")
    dominant_axis = str(multi_party_state.get("dominant_tension_axis") or "")

    edges: list[BridgeEdge] = []
    for pa, pb in combinations(parties, 2):
        if len(edges) >= _MAX_EDGES:
            break

        bridge_type = _infer_bridge_type(pa, pb, group_state)
        strength = _compute_bridge_strength(pa, pb)
        priority = _compute_bridge_priority(pa, pb, group_state)
        tension_axis = _primary_tension_axis(pa, pb, dominant_axis)
        reason = _bridge_reason(bridge_type, pa, pb, tension_axis)
        confidence = _edge_confidence(pa, pb)

        edges.append(BridgeEdge(
            from_party_id=str(pa.get("party_id") or ""),
            to_party_id=str(pb.get("party_id") or ""),
            bridge_type=bridge_type,
            tension_axis=tension_axis,
            bridge_strength=strength,
            bridge_priority=priority,
            bridge_reason=reason,
            confidence=confidence,
        ))

    # Sort by priority descending for consistent output
    edges.sort(key=lambda e: e.bridge_priority, reverse=True)
    return edges


def build_bridge_graph_state(
    multi_party_state: dict[str, Any],
    alignment_report: dict[str, Any] | None = None,
) -> BridgeGraphState:
    """Build a group-level bridge graph from multi_party_alignment_state.

    Never mutates its arguments. Never raises. Returns empty BridgeGraphState
    for invalid or insufficient input.

    Output schema via BridgeGraphState.to_dict():
    {
        "nodes": [str, ...],
        "edges": [{bridge_type, from_party_id, to_party_id, ...}, ...],
        "dominant_bridge_type": str,
        "highest_priority_edges": [{...}, ...],
        "bridge_density": float,
        "fragmentation_level": "low" | "medium" | "high",
        "summary_reason": str,
    }
    """
    if not isinstance(multi_party_state, dict):
        return BridgeGraphState(summary_reason="no multi_party_state provided")

    parties = [
        p for p in (multi_party_state.get("parties") or [])
        if isinstance(p, dict)
    ]
    nodes = [str(p.get("party_id") or "") for p in parties[:_MAX_PARTIES]]

    edges = build_bridge_edges(multi_party_state, alignment_report)
    edge_dicts = [e.to_dict() for e in edges]

    # Bridge density: actual edges / max possible edges for this party count
    n = len(nodes)
    max_edges = (n * (n - 1)) // 2 if n >= 2 else 0
    density = (len(edges) / max_edges) if max_edges > 0 else 0.0

    # Fragmentation level (inverse of density)
    if density <= _HIGH_FRAGMENTATION_EDGE_DENSITY or (n >= 2 and not edges):
        fragmentation = "high"
    elif density <= _MEDIUM_FRAGMENTATION_EDGE_DENSITY:
        fragmentation = "medium"
    else:
        fragmentation = "low"

    # Dominant bridge type: most common type across edges
    type_counts: dict[str, int] = {}
    for e in edges:
        type_counts[e.bridge_type] = type_counts.get(e.bridge_type, 0) + 1
    dominant_type = max(type_counts, key=lambda k: type_counts[k]) if type_counts else ""

    highest = edge_dicts[:_MAX_HIGHEST_PRIORITY]

    # Summary reason
    group_state = str(multi_party_state.get("state_label") or "stable")
    dominant_axis = str(multi_party_state.get("dominant_tension_axis") or "")
    parts: list[str] = [f"{n} part{'y' if n == 1 else 'ies'}"]
    parts.append(f"{len(edges)} edge{'s' if len(edges) != 1 else ''}")
    if dominant_type:
        parts.append(f"dominant: {dominant_type}")
    if dominant_axis:
        parts.append(f"axis: {dominant_axis}")
    parts.append(f"state: {group_state}")
    summary = "; ".join(parts)

    return BridgeGraphState(
        nodes=nodes,
        edges=edge_dicts,
        dominant_bridge_type=dominant_type,
        highest_priority_edges=highest,
        bridge_density=round(density, 4),
        fragmentation_level=fragmentation,
        summary_reason=summary,
    )


# ---------------------------------------------------------------------------
# Observability metrics
# ---------------------------------------------------------------------------

@dataclass
class BridgeGraphMetrics:
    calls_total: int = 0
    graph_states_total: int = 0
    edges_total: int = 0
    small_input_total: int = 0          # < 2 parties
    acknowledgment_bridge_total: int = 0
    pacing_bridge_total: int = 0
    reframing_bridge_total: int = 0
    translation_bridge_total: int = 0
    stabilization_bridge_total: int = 0
    high_fragmentation_total: int = 0
    _strength_sum: float = 0.0
    _priority_sum: float = 0.0

    @property
    def avg_bridge_strength(self) -> float:
        if self.edges_total == 0:
            return 0.0
        return round(self._strength_sum / self.edges_total, 4)

    @property
    def avg_bridge_priority(self) -> float:
        if self.edges_total == 0:
            return 0.0
        return round(self._priority_sum / self.edges_total, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls_total": self.calls_total,
            "graph_states_total": self.graph_states_total,
            "edges_total": self.edges_total,
            "small_input_total": self.small_input_total,
            "acknowledgment_bridge_total": self.acknowledgment_bridge_total,
            "pacing_bridge_total": self.pacing_bridge_total,
            "reframing_bridge_total": self.reframing_bridge_total,
            "translation_bridge_total": self.translation_bridge_total,
            "stabilization_bridge_total": self.stabilization_bridge_total,
            "high_fragmentation_total": self.high_fragmentation_total,
            "avg_bridge_strength": self.avg_bridge_strength,
            "avg_bridge_priority": self.avg_bridge_priority,
        }
