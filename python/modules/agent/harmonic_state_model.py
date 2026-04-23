# -*- coding: utf-8 -*-
"""Harmonic State Model MVP.

Builds a compact deterministic layer over:
- collective_coordination_snapshot
- bridge_stabilization_order
- bridge_playbook_advisory
- coordination_advisory_summary
- relational policy and coherence signals

Advisory-only:
- Never mutates inputs.
- Never modifies routing/control logic.
- No LLM, no embeddings, no external dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_MAX_REASON_CHARS = 140

_ALLOWED_CENTERS = {
    "coherence",
    "stabilization",
    "translation",
    "reframing",
    "exploration",
    "defense",
    "repair",
    "insufficient_context",
}
_ALLOWED_INTERVALS = {
    "unison",
    "third",
    "fifth",
    "fourth",
    "seventh",
    "tritone",
    "octave",
    "unknown",
}
_ALLOWED_RESOLUTION_DIRECTIONS = {
    "hold_course",
    "stabilize_then_continue",
    "deescalate_then_translate",
    "reframe_then_align",
    "repair_then_resume",
    "gather_context",
    "observe_and_stage",
    "translate_then_decide",
    "stabilize_then_reframe",
    "unknown",
}
_ALLOWED_MODULATION_CANDIDATES = {
    "none",
    "coherence",
    "stabilization",
    "translation",
    "reframing",
    "exploration",
    "defense",
    "repair",
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


def _is_effectively_empty(value: dict[str, Any] | None) -> bool:
    if not isinstance(value, dict) or not value:
        return True
    meaningful = [k for k, v in value.items() if k != "summary_reason" and v not in (None, "", [], {}, 0, 0.0)]
    return len(meaningful) == 0


def _first_ordered_edge(bridge_stabilization_order: dict[str, Any] | None) -> dict[str, Any] | None:
    bo = bridge_stabilization_order if isinstance(bridge_stabilization_order, dict) else {}
    ordered = [edge for edge in (bo.get("ordered_edges") or []) if isinstance(edge, dict)]
    return ordered[0] if ordered else None


def _stabilization_support(bridge_stabilization_order: dict[str, Any] | None) -> float:
    first = _first_ordered_edge(bridge_stabilization_order) or {}
    return _clamp01(_safe_float(first.get("stabilization_score"), 0.0))


def _playbook_support_score(bridge_playbook_advisory: dict[str, Any] | None) -> float:
    pa = bridge_playbook_advisory if isinstance(bridge_playbook_advisory, dict) else {}
    if "playbook_alignment_score" in pa:
        return _clamp01(_safe_float(pa.get("playbook_alignment_score"), 0.0))

    label = _norm(pa.get("playbook_alignment_label"))
    by_label = {
        "well_aligned": 0.9,
        "partially_aligned": 0.65,
        "weakly_aligned": 0.35,
        "misaligned": 0.1,
        "insufficient_context": 0.0,
    }
    return by_label.get(label, 0.0)


def _fragmentation_pressure(collective_coordination_snapshot: dict[str, Any] | None) -> float:
    cs = collective_coordination_snapshot if isinstance(collective_coordination_snapshot, dict) else {}
    frag = _norm(cs.get("group_fragmentation_level"))
    state = _norm(cs.get("coordination_state_label"))

    if frag == "high" or state in {"fragmented", "escalating"}:
        return 1.0
    if frag == "medium" or state in {"unstable", "strained"}:
        return 0.7
    if frag == "low" or state == "coherent":
        return 0.2
    return 0.4


def _adverse_route_pressure(
    coordination_advisory_summary: dict[str, Any] | None,
    relational_policy_decision: dict[str, Any] | None,
) -> float:
    summary = coordination_advisory_summary if isinstance(coordination_advisory_summary, dict) else {}
    relational = relational_policy_decision if isinstance(relational_policy_decision, dict) else {}

    label = _norm(summary.get("coordination_advisory_label"))
    risk_state = _norm(relational.get("risk_state"))

    pressure = {
        "ready": 0.15,
        "fragile": 0.75,
        "blocked": 1.0,
        "insufficient_context": 0.45,
    }.get(label, 0.45)

    risk_pressure = {
        "safe": 0.2,
        "watch": 0.65,
        "repair": 0.85,
        "escalate": 1.0,
    }.get(risk_state, 0.0)

    return max(pressure, risk_pressure)


def _derive_center(
    coordination_advisory_summary: dict[str, Any] | None,
    collective_coordination_snapshot: dict[str, Any] | None,
    relational_policy_decision: dict[str, Any] | None,
    *,
    insufficient: bool,
) -> str:
    if insufficient:
        return "insufficient_context"

    summary = coordination_advisory_summary if isinstance(coordination_advisory_summary, dict) else {}
    snapshot = collective_coordination_snapshot if isinstance(collective_coordination_snapshot, dict) else {}
    relational = relational_policy_decision if isinstance(relational_policy_decision, dict) else {}

    risk_state = _norm(relational.get("risk_state"))
    safety_mode = _norm(relational.get("safety_mode"))
    if risk_state == "repair":
        return "repair"
    if risk_state == "escalate" or safety_mode in {"human_first", "freeze"} or relational.get("requires_human_review"):
        return "defense"

    mode = _norm(summary.get("primary_intervention_mode"))
    mode_map = {
        "stabilization_first": "stabilization",
        "translation_first": "translation",
        "reframe_first": "reframing",
        "pacing_first": "exploration",
        "acknowledge_first": "coherence",
        "mixed": "exploration",
    }
    if mode in mode_map:
        return mode_map[mode]

    bridge_type = _norm(snapshot.get("dominant_bridge_type"))
    bridge_map = {
        "stabilization_bridge": "stabilization",
        "translation_bridge": "translation",
        "reframing_bridge": "reframing",
        "pacing_bridge": "exploration",
        "acknowledgment_bridge": "coherence",
    }
    if bridge_type in bridge_map:
        return bridge_map[bridge_type]

    if _norm(summary.get("coordination_advisory_label")) == "ready":
        return "coherence"
    return "exploration"


def _derive_modulation_candidate(
    *,
    harmonic_center: str,
    collective_coordination_snapshot: dict[str, Any] | None,
    bridge_playbook_advisory: dict[str, Any] | None,
    coordination_advisory_summary: dict[str, Any] | None,
    relational_policy_decision: dict[str, Any] | None,
    harmonic_tension: float,
    harmonic_stability: float,
    insufficient: bool,
) -> str:
    if insufficient:
        return "unknown"

    snapshot = collective_coordination_snapshot if isinstance(collective_coordination_snapshot, dict) else {}
    advisory = bridge_playbook_advisory if isinstance(bridge_playbook_advisory, dict) else {}
    summary = coordination_advisory_summary if isinstance(coordination_advisory_summary, dict) else {}
    relational = relational_policy_decision if isinstance(relational_policy_decision, dict) else {}

    risk_state = _norm(relational.get("risk_state"))
    safety_mode = _norm(relational.get("safety_mode"))
    top_risk_driver = _norm(summary.get("top_risk_driver"))
    dominant_fit = _norm(advisory.get("dominant_bridge_playbook_fit"))
    bridge_type = _norm(snapshot.get("dominant_bridge_type"))

    if risk_state == "repair":
        return "repair"
    if risk_state == "escalate" or safety_mode in {"human_first", "freeze"}:
        return "defense"
    if top_risk_driver == "playbook_misalignment" or dominant_fit == "reframing-led" or bridge_type == "reframing_bridge":
        return "reframing"
    if (
        top_risk_driver in {"fragmentation_pressure", "weak_bridge_support"}
        or dominant_fit == "translation-led"
        or bridge_type == "translation_bridge"
    ):
        return "translation"
    if harmonic_center in {"repair", "defense"} and harmonic_stability >= 0.58 and harmonic_tension <= 0.42:
        return "coherence"
    if harmonic_center == "reframing" and harmonic_stability >= 0.6 and harmonic_tension <= 0.38:
        return "coherence"
    if harmonic_center == "translation" and harmonic_stability >= harmonic_tension:
        return "none"
    if harmonic_center == "stabilization" and harmonic_tension <= 0.35 and harmonic_stability >= 0.68:
        return "none"
    if harmonic_tension <= 0.3 and harmonic_stability >= 0.7:
        return "none"
    return harmonic_center if harmonic_center in _ALLOWED_MODULATION_CANDIDATES else "unknown"


def _derive_interval_label(
    *,
    harmonic_center: str,
    modulation_candidate: str,
    harmonic_tension: float,
    harmonic_stability: float,
) -> str:
    if harmonic_center == "insufficient_context":
        return "unknown"
    if harmonic_tension <= 0.18 and harmonic_stability >= 0.82:
        return "unison"
    if harmonic_tension <= 0.32 and harmonic_stability >= 0.66:
        return "third"
    if harmonic_tension <= 0.5 and harmonic_stability >= 0.55:
        return "fifth"
    if harmonic_tension >= 0.75 and harmonic_stability <= 0.42:
        return "tritone"
    if harmonic_tension >= 0.6 and harmonic_stability <= 0.5:
        return "seventh"
    if (
        modulation_candidate not in {"none", "unknown", harmonic_center}
        and harmonic_tension >= 0.5
        and harmonic_stability >= 0.35
    ):
        return "octave"
    if abs(harmonic_tension - harmonic_stability) <= 0.12:
        return "fourth"
    return "fifth" if harmonic_stability >= harmonic_tension else "seventh"


def _derive_resolution_direction(
    *,
    harmonic_center: str,
    harmonic_interval_label: str,
    modulation_candidate: str,
) -> str:
    if harmonic_center == "insufficient_context":
        return "gather_context"
    if harmonic_center == "repair" or modulation_candidate == "repair":
        return "repair_then_resume"
    if harmonic_interval_label == "tritone":
        if modulation_candidate == "translation":
            return "deescalate_then_translate"
        if modulation_candidate == "reframing":
            return "stabilize_then_reframe"
        if modulation_candidate == "defense":
            return "observe_and_stage"
        return "stabilize_then_continue"
    if harmonic_interval_label == "unison":
        return "hold_course"
    if harmonic_center == "translation" or modulation_candidate == "translation":
        return "translate_then_decide"
    if harmonic_center == "reframing" or modulation_candidate == "reframing":
        return "reframe_then_align"
    if harmonic_interval_label == "fourth" or harmonic_center == "defense":
        return "observe_and_stage"
    if harmonic_center == "coherence" and modulation_candidate == "none":
        return "hold_course"
    if harmonic_center == "stabilization":
        return "stabilize_then_continue"
    return "unknown"


def _build_summary_reason(
    *,
    harmonic_center: str,
    harmonic_interval_label: str,
    modulation_candidate: str,
) -> str:
    if harmonic_center == "insufficient_context":
        return "insufficient coordination and relational context for harmonic state"

    target = modulation_candidate if modulation_candidate not in {"none", "unknown"} else harmonic_center
    if harmonic_interval_label == "tritone":
        reason = f"center is {harmonic_center}; scene is structurally dissonant and points toward {target}"
    elif harmonic_interval_label == "seventh":
        reason = f"center is {harmonic_center}; tension is rising and a controlled shift toward {target} may be needed"
    elif harmonic_interval_label == "fourth":
        reason = f"center is {harmonic_center}; scene is suspended between tension and stability, so pacing matters"
    elif harmonic_interval_label == "octave":
        reason = f"center is {harmonic_center}; pattern is reusable but likely needs a scale shift toward {target}"
    elif harmonic_interval_label == "unison":
        reason = f"center is {harmonic_center}; stability is high and no modulation is needed"
    else:
        reason = f"center is {harmonic_center}; scene is compatible and can progress with light guidance"

    reason = " ".join(reason.splitlines()).strip()
    if not reason:
        reason = "harmonic state summary generated"
    return reason[:_MAX_REASON_CHARS]


@dataclass
class HarmonicStateSummary:
    harmonic_center: str = "insufficient_context"
    harmonic_interval_label: str = "unknown"
    harmonic_tension: float = 0.0
    harmonic_stability: float = 0.0
    resolution_direction: str = "gather_context"
    modulation_candidate: str = "unknown"
    harmonic_summary_reason: str = "insufficient coordination and relational context for harmonic state"

    def to_dict(self) -> dict[str, Any]:
        center = self.harmonic_center if self.harmonic_center in _ALLOWED_CENTERS else "insufficient_context"
        interval = self.harmonic_interval_label if self.harmonic_interval_label in _ALLOWED_INTERVALS else "unknown"
        resolution = (
            self.resolution_direction
            if self.resolution_direction in _ALLOWED_RESOLUTION_DIRECTIONS
            else "unknown"
        )
        modulation = (
            self.modulation_candidate
            if self.modulation_candidate in _ALLOWED_MODULATION_CANDIDATES
            else "unknown"
        )
        reason = " ".join(str(self.harmonic_summary_reason or "").splitlines()).strip()
        if not reason:
            reason = "insufficient coordination and relational context for harmonic state"

        return {
            "harmonic_center": center,
            "harmonic_interval_label": interval,
            "harmonic_tension": round(_clamp01(self.harmonic_tension), 4),
            "harmonic_stability": round(_clamp01(self.harmonic_stability), 4),
            "resolution_direction": resolution,
            "modulation_candidate": modulation,
            "harmonic_summary_reason": reason[:_MAX_REASON_CHARS],
        }


@dataclass
class HarmonicStateMetrics:
    calls_total: int = 0
    summaries_total: int = 0
    coherence_center_total: int = 0
    stabilization_center_total: int = 0
    translation_center_total: int = 0
    reframing_center_total: int = 0
    exploration_center_total: int = 0
    defense_center_total: int = 0
    repair_center_total: int = 0
    insufficient_context_total: int = 0
    unison_total: int = 0
    third_total: int = 0
    fifth_total: int = 0
    fourth_total: int = 0
    seventh_total: int = 0
    tritone_total: int = 0
    octave_total: int = 0
    modulation_total: int = 0
    _tension_sum: float = 0.0
    _stability_sum: float = 0.0

    @property
    def avg_harmonic_tension(self) -> float:
        if self.summaries_total <= 0:
            return 0.0
        return round(self._tension_sum / self.summaries_total, 4)

    @property
    def avg_harmonic_stability(self) -> float:
        if self.summaries_total <= 0:
            return 0.0
        return round(self._stability_sum / self.summaries_total, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls_total": self.calls_total,
            "summaries_total": self.summaries_total,
            "coherence_center_total": self.coherence_center_total,
            "stabilization_center_total": self.stabilization_center_total,
            "translation_center_total": self.translation_center_total,
            "reframing_center_total": self.reframing_center_total,
            "exploration_center_total": self.exploration_center_total,
            "defense_center_total": self.defense_center_total,
            "repair_center_total": self.repair_center_total,
            "insufficient_context_total": self.insufficient_context_total,
            "unison_total": self.unison_total,
            "third_total": self.third_total,
            "fifth_total": self.fifth_total,
            "fourth_total": self.fourth_total,
            "seventh_total": self.seventh_total,
            "tritone_total": self.tritone_total,
            "octave_total": self.octave_total,
            "modulation_total": self.modulation_total,
            "avg_harmonic_tension": self.avg_harmonic_tension,
            "avg_harmonic_stability": self.avg_harmonic_stability,
        }


def build_harmonic_state_summary(
    *,
    collective_coordination_snapshot: dict[str, Any] | None = None,
    bridge_stabilization_order: dict[str, Any] | None = None,
    bridge_playbook_advisory: dict[str, Any] | None = None,
    coordination_advisory_summary: dict[str, Any] | None = None,
    relational_policy_decision: dict[str, Any] | None = None,
    relational_coherence: float | None = None,
) -> HarmonicStateSummary:
    """Build a deterministic harmonic summary over coordination and relational state."""
    cs = collective_coordination_snapshot if isinstance(collective_coordination_snapshot, dict) else {}
    bo = bridge_stabilization_order if isinstance(bridge_stabilization_order, dict) else {}
    pa = bridge_playbook_advisory if isinstance(bridge_playbook_advisory, dict) else {}
    summary = coordination_advisory_summary if isinstance(coordination_advisory_summary, dict) else {}
    relational = relational_policy_decision if isinstance(relational_policy_decision, dict) else {}

    insufficient = all(
        _is_effectively_empty(value)
        for value in (cs, bo, pa, summary, relational)
    ) and relational_coherence is None

    if insufficient:
        return HarmonicStateSummary()

    coordination_risk = _clamp01(_safe_float(cs.get("coordination_risk"), 0.0))
    coherence = _clamp01(_safe_float(relational_coherence, 0.5))
    playbook_support = _playbook_support_score(pa)
    stabilization_support = _stabilization_support(bo)
    stabilization_grounding = min(stabilization_support, playbook_support) if playbook_support > 0.0 else 0.0
    fragmentation_score = _fragmentation_pressure(cs)
    adverse_pressure = _adverse_route_pressure(summary, relational)
    readiness = _clamp01(_safe_float(summary.get("coordination_readiness"), 0.0))

    harmonic_tension = _clamp01(
        (0.35 * coordination_risk)
        + (0.25 * (1.0 - coherence))
        + (0.20 * fragmentation_score)
        + (0.20 * adverse_pressure)
    )
    harmonic_stability = _clamp01(
        (0.4 * coherence)
        + (0.25 * playbook_support)
        + (0.2 * stabilization_grounding)
        + (0.15 * readiness)
    )

    harmonic_center = _derive_center(
        summary,
        cs,
        relational,
        insufficient=insufficient,
    )
    modulation_candidate = _derive_modulation_candidate(
        harmonic_center=harmonic_center,
        collective_coordination_snapshot=cs,
        bridge_playbook_advisory=pa,
        coordination_advisory_summary=summary,
        relational_policy_decision=relational,
        harmonic_tension=harmonic_tension,
        harmonic_stability=harmonic_stability,
        insufficient=insufficient,
    )
    harmonic_interval_label = _derive_interval_label(
        harmonic_center=harmonic_center,
        modulation_candidate=modulation_candidate,
        harmonic_tension=harmonic_tension,
        harmonic_stability=harmonic_stability,
    )
    resolution_direction = _derive_resolution_direction(
        harmonic_center=harmonic_center,
        harmonic_interval_label=harmonic_interval_label,
        modulation_candidate=modulation_candidate,
    )
    harmonic_summary_reason = _build_summary_reason(
        harmonic_center=harmonic_center,
        harmonic_interval_label=harmonic_interval_label,
        modulation_candidate=modulation_candidate,
    )

    return HarmonicStateSummary(
        harmonic_center=harmonic_center,
        harmonic_interval_label=harmonic_interval_label,
        harmonic_tension=harmonic_tension,
        harmonic_stability=harmonic_stability,
        resolution_direction=resolution_direction,
        modulation_candidate=modulation_candidate,
        harmonic_summary_reason=harmonic_summary_reason,
    )
