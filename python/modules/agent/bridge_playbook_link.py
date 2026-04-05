# -*- coding: utf-8 -*-
"""Bridge-to-Playbook Advisory Link MVP.

Builds a compact deterministic advisory layer linking existing structured layers:
- alignment_strategy_playbook
- bridge_graph_state
- bridge_stabilization_order
- collective_coordination_snapshot

Advisory-only:
- Never mutates inputs.
- Never changes routing / graph / backend / reuse logic.
- Never rewrites playbook or recommendations.
- No LLM, no embeddings, no external dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_MAX_STEP_LINKS = 10
_MAX_TOP_SUPPORTED = 3
_MAX_TOP_WEAK = 3
_MAX_REASON_CHARS = 140

_LINK_STRONG = "strong_fit"
_LINK_PARTIAL = "partial_fit"
_LINK_WEAK = "weak_fit"
_LINK_UNSUPPORTED = "unsupported"
_LINK_INSUFFICIENT = "insufficient_context"

_ALIGNMENT_WELL = "well_aligned"
_ALIGNMENT_PARTIAL = "partially_aligned"
_ALIGNMENT_WEAK = "weakly_aligned"
_ALIGNMENT_MISALIGNED = "misaligned"
_ALIGNMENT_INSUFFICIENT = "insufficient_context"

_BRIDGE_PLAYBOOK_MAP: dict[str, list[str]] = {
    "acknowledgment_bridge": [
        "acknowledge",
        "recognition",
        "recognize",
        "shared concern",
        "name the",
        "tension",
    ],
    "pacing_bridge": [
        "slow",
        "slowing",
        "pace",
        "timing",
        "not rushing",
        "pause",
    ],
    "reframing_bridge": [
        "reframe",
        "reframing",
        "winner/loser",
        "not winner",
        "mismatch framing",
        "shared goal",
    ],
    "translation_bridge": [
        "translate",
        "translating",
        "models",
        "lenses",
        "clarify",
        "separate",
        "internal causes",
    ],
    "stabilization_bridge": [
        "de-escalation",
        "deescalation",
        "lowering pressure",
        "restore safety",
        "stabilize",
        "stabilization",
    ],
}

_BRIDGE_TO_FIT_LABEL = {
    "acknowledgment_bridge": "acknowledgment-led",
    "pacing_bridge": "pacing-led",
    "reframing_bridge": "reframing-led",
    "translation_bridge": "translation-led",
    "stabilization_bridge": "stabilization-led",
}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _norm(text: Any) -> str:
    return str(text or "").strip().lower()


def _extract_playbook_steps(playbook: dict[str, Any] | None) -> list[dict[str, Any]]:
    pb = playbook if isinstance(playbook, dict) else {}
    raw_steps = [s for s in (pb.get("steps") or []) if isinstance(s, dict)]
    steps: list[dict[str, Any]] = []
    for idx, step in enumerate(raw_steps[:_MAX_STEP_LINKS], start=1):
        phase = str(step.get("phase") or f"step_{idx}")
        actions = [str(a).strip() for a in (step.get("actions") or []) if str(a).strip()]
        text = " | ".join(actions) if actions else phase.replace("_", " ")
        steps.append({
            "step_id": f"{phase}:{idx}",
            "step_text": text[:240],
        })
    return steps


def _bridge_presence(bridge_graph_state: dict[str, Any] | None) -> set[str]:
    bg = bridge_graph_state if isinstance(bridge_graph_state, dict) else {}
    edges = [e for e in (bg.get("edges") or []) if isinstance(e, dict)]
    present: set[str] = set()
    for edge in edges:
        b = str(edge.get("bridge_type") or "").strip()
        if b:
            present.add(b)
    return present


def _dominant_bridge(bridge_graph_state: dict[str, Any] | None, collective_snapshot: dict[str, Any] | None) -> str:
    bg = bridge_graph_state if isinstance(bridge_graph_state, dict) else {}
    high = [e for e in (bg.get("highest_priority_edges") or []) if isinstance(e, dict)]
    if high:
        return str(high[0].get("bridge_type") or "")

    edges = [e for e in (bg.get("edges") or []) if isinstance(e, dict)]
    if edges:
        return str(edges[0].get("bridge_type") or "")

    cs = collective_snapshot if isinstance(collective_snapshot, dict) else {}
    snap_bridge = str(cs.get("dominant_bridge_type") or "").strip()
    if snap_bridge:
        return snap_bridge
    return ""


def _dominant_stabilization_label(
    bridge_stabilization_order: dict[str, Any] | None,
) -> str:
    bo = bridge_stabilization_order if isinstance(bridge_stabilization_order, dict) else {}
    ordered = [e for e in (bo.get("ordered_edges") or []) if isinstance(e, dict)]
    if not ordered:
        return ""
    return str(ordered[0].get("stabilization_label") or "")


def _match_bridge_types(step_text: str) -> list[str]:
    t = _norm(step_text)
    matched: list[str] = []
    for bridge_type, cues in _BRIDGE_PLAYBOOK_MAP.items():
        for cue in cues:
            if cue in t:
                matched.append(bridge_type)
                break
    return matched


@dataclass
class BridgePlaybookLinkEntry:
    playbook_step_id: str
    playbook_step_text: str
    linked_bridge_type: str
    linked_stabilization_label: str
    link_strength: float
    link_label: str
    link_reason: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "playbook_step_id": self.playbook_step_id,
            "playbook_step_text": self.playbook_step_text,
            "linked_bridge_type": self.linked_bridge_type,
            "linked_stabilization_label": self.linked_stabilization_label,
            "link_strength": round(_clamp01(self.link_strength), 4),
            "link_label": self.link_label,
            "link_reason": self.link_reason,
            "confidence": round(_clamp01(self.confidence), 4),
        }


@dataclass
class BridgePlaybookAdvisory:
    playbook_alignment_label: str = _ALIGNMENT_INSUFFICIENT
    playbook_alignment_score: float = 0.0
    step_links: list[dict[str, Any]] = field(default_factory=list)
    top_supported_steps: list[dict[str, Any]] = field(default_factory=list)
    top_weak_steps: list[dict[str, Any]] = field(default_factory=list)
    dominant_bridge_playbook_fit: str = "unknown"
    summary_reason: str = "insufficient context for bridge-playbook advisory"

    def to_dict(self) -> dict[str, Any]:
        return {
            "playbook_alignment_label": self.playbook_alignment_label,
            "playbook_alignment_score": round(_clamp01(self.playbook_alignment_score), 4),
            "step_links": self.step_links,
            "top_supported_steps": self.top_supported_steps,
            "top_weak_steps": self.top_weak_steps,
            "dominant_bridge_playbook_fit": self.dominant_bridge_playbook_fit,
            "summary_reason": self.summary_reason,
        }


@dataclass
class BridgePlaybookMetrics:
    calls_total: int = 0
    advisories_total: int = 0
    step_links_total: int = 0
    strong_fit_total: int = 0
    partial_fit_total: int = 0
    weak_fit_total: int = 0
    unsupported_total: int = 0
    insufficient_context_total: int = 0
    _alignment_score_sum: float = 0.0
    nonempty_supported_steps_total: int = 0
    nonempty_weak_steps_total: int = 0
    well_aligned_total: int = 0
    partially_aligned_total: int = 0
    weakly_aligned_total: int = 0
    misaligned_total: int = 0

    @property
    def avg_playbook_alignment_score(self) -> float:
        if self.advisories_total <= 0:
            return 0.0
        return round(self._alignment_score_sum / self.advisories_total, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls_total": self.calls_total,
            "advisories_total": self.advisories_total,
            "step_links_total": self.step_links_total,
            "strong_fit_total": self.strong_fit_total,
            "partial_fit_total": self.partial_fit_total,
            "weak_fit_total": self.weak_fit_total,
            "unsupported_total": self.unsupported_total,
            "insufficient_context_total": self.insufficient_context_total,
            "avg_playbook_alignment_score": self.avg_playbook_alignment_score,
            "nonempty_supported_steps_total": self.nonempty_supported_steps_total,
            "nonempty_weak_steps_total": self.nonempty_weak_steps_total,
            "well_aligned_total": self.well_aligned_total,
            "partially_aligned_total": self.partially_aligned_total,
            "weakly_aligned_total": self.weakly_aligned_total,
            "misaligned_total": self.misaligned_total,
        }


def _match_playbook_step_to_scene(
    step_text: str,
    bridge_graph_state: dict[str, Any] | None,
    bridge_stabilization_order: dict[str, Any] | None,
    collective_snapshot: dict[str, Any] | None,
    *,
    step_id: str,
) -> BridgePlaybookLinkEntry:
    """Deterministically link one playbook step to scene-level bridge signals.

    Matching is graph-first lexical bridge matching with stabilization-aware
    adjustments (urgent/early stabilization can amplify stabilization-linked
    steps). No LLM / semantic embeddings.
    """
    bridge_present = _bridge_presence(bridge_graph_state)
    dominant_bridge = _dominant_bridge(bridge_graph_state, collective_snapshot)
    stabilization_label = _dominant_stabilization_label(bridge_stabilization_order)
    matched_types = _match_bridge_types(step_text)

    if not step_text.strip():
        return BridgePlaybookLinkEntry(
            playbook_step_id=step_id,
            playbook_step_text="",
            linked_bridge_type="unknown",
            linked_stabilization_label=stabilization_label or "unknown",
            link_strength=0.0,
            link_label=_LINK_INSUFFICIENT,
            link_reason="empty playbook step text",
            confidence=0.0,
        )

    if not bridge_present and not dominant_bridge:
        label = _LINK_INSUFFICIENT
        strength = 0.15 if matched_types else 0.0
        return BridgePlaybookLinkEntry(
            playbook_step_id=step_id,
            playbook_step_text=step_text,
            linked_bridge_type=(matched_types[0] if matched_types else "unknown"),
            linked_stabilization_label=stabilization_label or "unknown",
            link_strength=strength,
            link_label=label,
            link_reason="playbook cues detected, but bridge scene context is missing"[:_MAX_REASON_CHARS],
            confidence=0.2 if matched_types else 0.1,
        )

    chosen_bridge = ""
    strength = 0.18
    label = _LINK_WEAK

    if matched_types:
        for bridge_type in matched_types:
            if bridge_type == dominant_bridge and bridge_type in bridge_present:
                chosen_bridge = bridge_type
                strength = 0.93
                label = _LINK_STRONG
                break
        if not chosen_bridge:
            for bridge_type in matched_types:
                if bridge_type in bridge_present:
                    chosen_bridge = bridge_type
                    strength = 0.69
                    label = _LINK_PARTIAL
                    break
        if not chosen_bridge:
            chosen_bridge = matched_types[0]
            if dominant_bridge and chosen_bridge != dominant_bridge:
                strength = 0.22
                label = _LINK_UNSUPPORTED
            else:
                strength = 0.38
                label = _LINK_WEAK
    else:
        chosen_bridge = dominant_bridge or "unknown"
        if chosen_bridge and chosen_bridge in bridge_present:
            strength = 0.32
            label = _LINK_WEAK
        else:
            strength = 0.12
            label = _LINK_INSUFFICIENT

    if (
        chosen_bridge == "stabilization_bridge"
        and stabilization_label in {"urgent_stabilize", "early_stabilize"}
        and label in {_LINK_PARTIAL, _LINK_STRONG, _LINK_WEAK}
    ):
        strength = _clamp01(strength + 0.08)
        if label == _LINK_WEAK and strength >= 0.40:
            label = _LINK_PARTIAL

    confidence = 0.5
    if label == _LINK_STRONG:
        confidence = 0.94
    elif label == _LINK_PARTIAL:
        confidence = 0.78
    elif label == _LINK_UNSUPPORTED:
        confidence = 0.62
    elif label == _LINK_WEAK:
        confidence = 0.55
    elif label == _LINK_INSUFFICIENT:
        confidence = 0.2

    reason = (
        f"label={label}; bridge={chosen_bridge or 'unknown'}; "
        f"dominant={dominant_bridge or 'unknown'}; matched={len(matched_types)}"
    )

    return BridgePlaybookLinkEntry(
        playbook_step_id=step_id,
        playbook_step_text=step_text,
        linked_bridge_type=chosen_bridge or "unknown",
        linked_stabilization_label=stabilization_label or "unknown",
        link_strength=_clamp01(strength),
        link_label=label,
        link_reason=reason[:_MAX_REASON_CHARS],
        confidence=_clamp01(confidence),
    )


def _compute_playbook_alignment_score(
    step_links: list[dict[str, Any]],
    collective_snapshot: dict[str, Any] | None = None,
) -> float:
    if not step_links:
        return 0.0

    strong = sum(1 for s in step_links if s.get("link_label") == _LINK_STRONG)
    partial = sum(1 for s in step_links if s.get("link_label") == _LINK_PARTIAL)
    weak = sum(1 for s in step_links if s.get("link_label") == _LINK_WEAK)
    unsupported = sum(1 for s in step_links if s.get("link_label") == _LINK_UNSUPPORTED)
    insufficient = sum(1 for s in step_links if s.get("link_label") == _LINK_INSUFFICIENT)
    total = len(step_links)

    score = 0.0
    score += 0.74 * (strong / total)
    score += 0.42 * (partial / total)
    score += 0.20 * (weak / total)
    score -= 0.48 * (unsupported / total)
    score -= 0.20 * (insufficient / total)

    cs = collective_snapshot if isinstance(collective_snapshot, dict) else {}
    dom_bridge = str(cs.get("dominant_bridge_type") or "")
    if dom_bridge:
        dom_hits = sum(1 for s in step_links if s.get("linked_bridge_type") == dom_bridge)
        score += 0.12 * (dom_hits / total)

    risk = _safe_float(cs.get("coordination_risk"), 0.0)
    if risk >= 0.75 and strong == 0 and partial <= 1:
        score -= 0.10

    return round(_clamp01(score), 4)


def _label_playbook_alignment(
    step_links: list[dict[str, Any]],
    collective_snapshot: dict[str, Any] | None = None,
) -> tuple[str, float]:
    if not step_links:
        return _ALIGNMENT_INSUFFICIENT, 0.0

    score = _compute_playbook_alignment_score(step_links, collective_snapshot)
    total = len(step_links)
    strong = sum(1 for s in step_links if s.get("link_label") == _LINK_STRONG)
    unsupported = sum(1 for s in step_links if s.get("link_label") == _LINK_UNSUPPORTED)
    insufficient = sum(1 for s in step_links if s.get("link_label") == _LINK_INSUFFICIENT)

    if insufficient >= total:
        return _ALIGNMENT_INSUFFICIENT, score
    if strong >= max(2, total // 2) and score >= 0.62:
        return _ALIGNMENT_WELL, score
    if unsupported >= max(2, total // 2) and score <= 0.30:
        return _ALIGNMENT_MISALIGNED, score
    if score >= 0.45:
        return _ALIGNMENT_PARTIAL, score
    if score <= 0.20 and unsupported > 0:
        return _ALIGNMENT_MISALIGNED, score
    return _ALIGNMENT_WEAK, score


def _dominant_bridge_playbook_fit(step_links: list[dict[str, Any]]) -> str:
    if not step_links:
        return "unknown"

    weighted: dict[str, float] = {}
    for step in step_links:
        bridge_type = str(step.get("linked_bridge_type") or "")
        if bridge_type not in _BRIDGE_TO_FIT_LABEL:
            continue
        if step.get("link_label") in {_LINK_UNSUPPORTED, _LINK_INSUFFICIENT}:
            continue
        weighted[bridge_type] = weighted.get(bridge_type, 0.0) + _safe_float(step.get("link_strength"), 0.0)

    if not weighted:
        return "unknown"

    top = sorted(weighted.items(), key=lambda x: (-x[1], x[0]))
    if len(top) >= 2 and abs(top[0][1] - top[1][1]) <= 0.12:
        return "mixed"
    return _BRIDGE_TO_FIT_LABEL.get(top[0][0], "unknown")


def _build_playbook_advisory_reason(fields: dict[str, Any]) -> str:
    label = str(fields.get("playbook_alignment_label") or _ALIGNMENT_INSUFFICIENT)
    fit = str(fields.get("dominant_bridge_playbook_fit") or "unknown")
    supported = int(fields.get("supported_count") or 0)
    weak = int(fields.get("weak_count") or 0)

    if label == _ALIGNMENT_WELL:
        return f"playbook strongly matches current bridge scene ({fit})"
    if label == _ALIGNMENT_PARTIAL:
        return f"playbook partially matches dominant scene signals ({fit}); weak steps={weak}"
    if label == _ALIGNMENT_WEAK:
        return f"playbook support is limited in current coordination scene ({fit}); weak steps={weak}"
    if label == _ALIGNMENT_MISALIGNED:
        return "current scene needs diverge from playbook direction; stabilization-fit remains low"
    if supported > 0:
        return "limited bridge context; only partial playbook grounding is available"
    return "insufficient bridge-playbook context for reliable advisory"


def build_bridge_playbook_advisory(
    playbook: dict[str, Any] | None = None,
    bridge_graph_state: dict[str, Any] | None = None,
    bridge_stabilization_order: dict[str, Any] | None = None,
    collective_snapshot: dict[str, Any] | None = None,
) -> BridgePlaybookAdvisory:
    steps = _extract_playbook_steps(playbook)
    if not steps:
        return BridgePlaybookAdvisory(
            playbook_alignment_label=_ALIGNMENT_INSUFFICIENT,
            playbook_alignment_score=0.0,
            step_links=[],
            top_supported_steps=[],
            top_weak_steps=[],
            dominant_bridge_playbook_fit="unknown",
            summary_reason="no playbook steps available for bridge advisory",
        )

    links: list[dict[str, Any]] = []
    for step in steps[:_MAX_STEP_LINKS]:
        link = _match_playbook_step_to_scene(
            step["step_text"],
            bridge_graph_state,
            bridge_stabilization_order,
            collective_snapshot,
            step_id=step["step_id"],
        )
        links.append(link.to_dict())

    label, score = _label_playbook_alignment(links, collective_snapshot)

    supported = [
        s
        for s in links
        if s.get("link_label") in {_LINK_STRONG, _LINK_PARTIAL}
    ]
    supported.sort(
        key=lambda e: (-_safe_float(e.get("link_strength")), e.get("playbook_step_id") or "")
    )
    top_supported = [
        {
            "playbook_step_id": str(s.get("playbook_step_id") or ""),
            "link_label": str(s.get("link_label") or ""),
            "linked_bridge_type": str(s.get("linked_bridge_type") or ""),
            "link_strength": round(_clamp01(_safe_float(s.get("link_strength"), 0.0)), 4),
        }
        for s in supported[:_MAX_TOP_SUPPORTED]
    ]

    weak = [
        s
        for s in links
        if s.get("link_label") in {_LINK_WEAK, _LINK_UNSUPPORTED, _LINK_INSUFFICIENT}
    ]
    weak.sort(
        key=lambda e: (_safe_float(e.get("link_strength"), 0.0), e.get("playbook_step_id") or "")
    )
    top_weak = [
        {
            "playbook_step_id": str(s.get("playbook_step_id") or ""),
            "link_label": str(s.get("link_label") or ""),
            "linked_bridge_type": str(s.get("linked_bridge_type") or ""),
            "link_strength": round(_clamp01(_safe_float(s.get("link_strength"), 0.0)), 4),
        }
        for s in weak[:_MAX_TOP_WEAK]
    ]

    fit = _dominant_bridge_playbook_fit(links)
    supported_count = len(supported)
    weak_count = len(weak)
    summary = _build_playbook_advisory_reason(
        {
            "playbook_alignment_label": label,
            "dominant_bridge_playbook_fit": fit,
            "supported_count": supported_count,
            "weak_count": weak_count,
        }
    )[:_MAX_REASON_CHARS]

    return BridgePlaybookAdvisory(
        playbook_alignment_label=label,
        playbook_alignment_score=score,
        step_links=links,
        top_supported_steps=top_supported,
        top_weak_steps=top_weak,
        dominant_bridge_playbook_fit=fit,
        summary_reason=summary,
    )
