# -*- coding: utf-8 -*-
"""Multi-party alignment state MVP — per-party descriptive snapshot.

Reads already-computed alignment report and optional adoption traces to build
a structured, per-party state description for the current cycle.

Advisory/read-only layer: never mutates alignment_report, recommendations,
routing decisions, graph_mode, route_key, reuse/refine/full_run, or any
upstream pipeline state.  Pure functions only.  No LLM, no embeddings.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_PARTIES = 5
_MAX_TENSION_AXES_PER_PARTY = 4

# State label thresholds (deterministic, fixed)
_ESCALATING_TENSION = 0.65
_DIVERGING_TENSION = 0.45
_CONVERGING_ALIGNMENT = 0.60


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_party_ids(alignment_report: dict[str, Any]) -> list[str]:
    """Extract ordered, deduplicated party IDs from the alignment report.

    Priority: report["participants"] → flatten(hotspot["participants"]).
    """
    seen: dict[str, None] = {}  # ordered-set via dict

    # Primary source: structured participants list
    for p in (alignment_report.get("participants") or []):
        pid: str = ""
        if isinstance(p, dict):
            pid = str(p.get("participant_id") or p.get("id") or "")
        elif isinstance(p, str):
            pid = p
        if pid and pid not in seen:
            seen[pid] = None

    # Fallback: extract from pairwise hotspots
    if not seen:
        for hotspot in (alignment_report.get("pairwise_hotspots") or []):
            for pid in (hotspot.get("participants") or []):
                s = str(pid)
                if s and s not in seen:
                    seen[s] = None

    parties = list(seen.keys())[:_MAX_PARTIES]
    return parties


def _hotspots_for_party(
    party_id: str,
    hotspots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        h for h in hotspots
        if party_id in (h.get("participants") or [])
    ]


def _position_label(
    party_id: str,
    hotspots_for_party: list[dict[str, Any]],
    total_hotspots: int,
    overall_alignment: float,
) -> str:
    """One-word label describing this party's alignment posture.

    Labels (mutually exclusive, priority order):
    - aligned        — low personal tension, high agreement
    - tension_source — appears in most hotspots, high average tension
    - responsive     — appears in some hotspots but mostly alignment-side
    - neutral        — little or no hotspot involvement
    """
    if not hotspots_for_party:
        if overall_alignment >= 0.60:
            return "aligned"
        return "neutral"

    avg_tension = sum(
        float(h.get("tension") or 0.0) for h in hotspots_for_party
    ) / len(hotspots_for_party)

    avg_alignment = sum(
        float(h.get("alignment") or 0.0) for h in hotspots_for_party
    ) / len(hotspots_for_party)

    hotspot_ratio = len(hotspots_for_party) / max(total_hotspots, 1)

    if avg_tension >= 0.55 and hotspot_ratio >= 0.5:
        return "tension_source"
    if avg_alignment >= avg_tension:
        return "responsive"
    if overall_alignment >= 0.60:
        return "aligned"
    return "neutral"


def _tension_axes_for_party(hotspots: list[dict[str, Any]]) -> list[str]:
    """Collect unique mismatch reasons across all hotspots for this party."""
    seen: dict[str, None] = {}
    for h in hotspots:
        for reason in (h.get("mismatch_reasons") or []):
            s = str(reason)
            if s and s not in seen:
                seen[s] = None
    return list(seen.keys())[:_MAX_TENSION_AXES_PER_PARTY]


def _alignment_gap(hotspots_for_party: list[dict[str, Any]]) -> float:
    """1 - mean(alignment) across all hotspots involving this party."""
    if not hotspots_for_party:
        return 0.0
    mean_align = sum(
        float(h.get("alignment") or 0.0) for h in hotspots_for_party
    ) / len(hotspots_for_party)
    return round(max(0.0, min(1.0, 1.0 - mean_align)), 4)


def _state_label(mean_tension: float, mean_alignment: float) -> str:
    if mean_tension >= _ESCALATING_TENSION:
        return "escalating"
    if mean_tension >= _DIVERGING_TENSION:
        return "diverging"
    if mean_alignment >= _CONVERGING_ALIGNMENT:
        return "converging"
    return "stable"


def _adoption_coverage(adoption_traces: list[dict[str, Any]]) -> float:
    """Mean adoption_score across all adoption traces (0.0 if none)."""
    if not adoption_traces:
        return 0.0
    scores = [float(t.get("adoption_score") or 0.0) for t in adoption_traces]
    return round(sum(scores) / len(scores), 4)


def _dominant_tension_axis(hotspots: list[dict[str, Any]]) -> str:
    """Most-frequent mismatch reason across all hotspots, or empty string."""
    freq: dict[str, int] = {}
    for h in hotspots:
        for reason in (h.get("mismatch_reasons") or []):
            s = str(reason)
            freq[s] = freq.get(s, 0) + 1
    if not freq:
        return ""
    return max(freq, key=lambda k: freq[k])


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------

def build_multi_party_alignment_state(
    alignment_report: dict[str, Any],
    *,
    adoption_traces: list[dict[str, Any]] | None = None,
    recommendations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a per-party alignment state snapshot for the current cycle.

    Reads structured data from alignment_report and optional adoption_traces.
    Never mutates its arguments. Never raises. Returns a stable schema dict.

    Output schema
    -------------
    {
        "parties": [
            {
                "party_id": str,
                "position_label": "aligned|tension_source|responsive|neutral",
                "tension_axes": [str, ...],   # mismatch reason strings
                "alignment_gap": float,        # 0.0 = fully aligned, 1.0 = fully gapped
                "hotspot_count": int,
            },
            ...
        ],
        "party_count": int,
        "alignment_convergence": float,       # mean alignment across all pairs
        "dominant_tension_axis": str,
        "state_label": "converging|stable|diverging|escalating",
        "state_description": str,
        "adoption_coverage": float,           # mean adoption_score from traces
    }
    """
    report = alignment_report if isinstance(alignment_report, dict) else {}
    traces = adoption_traces if isinstance(adoption_traces, list) else []

    hotspots: list[dict[str, Any]] = [
        h for h in (report.get("pairwise_hotspots") or [])
        if isinstance(h, dict)
    ]
    overall_alignment = float(report.get("alignment_score") or 0.0)
    overall_tension = float(report.get("tension_score") or 0.0)

    party_ids = _extract_party_ids(report)

    parties: list[dict[str, Any]] = []
    for pid in party_ids:
        ph = _hotspots_for_party(pid, hotspots)
        parties.append({
            "party_id": pid,
            "position_label": _position_label(pid, ph, len(hotspots), overall_alignment),
            "tension_axes": _tension_axes_for_party(ph),
            "alignment_gap": _alignment_gap(ph),
            "hotspot_count": len(ph),
        })

    dominant = _dominant_tension_axis(hotspots)
    state = _state_label(overall_tension, overall_alignment)
    party_count = len(parties)

    desc_parts: list[str] = [f"{party_count} part{'y' if party_count == 1 else 'ies'} active"]
    if dominant:
        desc_parts.append(f"dominant axis: {dominant}")
    if hotspots:
        desc_parts.append(f"{len(hotspots)} hotspot{'s' if len(hotspots) != 1 else ''}")
    state_description = "; ".join(desc_parts)

    return {
        "parties": parties,
        "party_count": party_count,
        "alignment_convergence": round(overall_alignment, 4),
        "dominant_tension_axis": dominant,
        "state_label": state,
        "state_description": state_description,
        "adoption_coverage": _adoption_coverage(traces),
    }


# ---------------------------------------------------------------------------
# Observability metrics
# ---------------------------------------------------------------------------

@dataclass
class MultiPartyAlignmentMetrics:
    calls_total: int = 0
    empty_report_total: int = 0
    parties_seen_total: int = 0
    escalating_total: int = 0
    diverging_total: int = 0
    converging_total: int = 0
    stable_total: int = 0
    hotspots_processed_total: int = 0

    def to_dict(self) -> dict[str, Any]:
        avg_parties = (
            round(self.parties_seen_total / (self.calls_total - self.empty_report_total), 3)
            if (self.calls_total - self.empty_report_total) > 0
            else 0.0
        )
        return {
            "calls_total": self.calls_total,
            "empty_report_total": self.empty_report_total,
            "parties_seen_total": self.parties_seen_total,
            "avg_parties_per_nonempty": avg_parties,
            "escalating_total": self.escalating_total,
            "diverging_total": self.diverging_total,
            "converging_total": self.converging_total,
            "stable_total": self.stable_total,
            "hotspots_processed_total": self.hotspots_processed_total,
        }
