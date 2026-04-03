# -*- coding: utf-8 -*-
"""Alignment memory units — per-cycle explainable memory for alignment outcomes.

Intentionally a standalone helper: stdlib-only imports, no dependency on
routing, graph, or LLM modules.  All writes are best-effort; errors never
propagate to callers.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core dataclasses
# ---------------------------------------------------------------------------


@dataclass
class AlignmentMemoryUnit:
    """Compact, explainable snapshot of one alignment-related pipeline cycle."""

    source_question: str
    intent: str | None
    why: str | None
    alignment_hotspot: str | None
    mismatch_reasons: list[str]
    guidance_applied: bool
    softening_detected: bool
    softening_signals: list[str]
    effect_reason: str | None
    guidance_effective: bool
    response_score: float
    goal_alignment_score: float
    tension_score_before: float | None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_question": self.source_question,
            "intent": self.intent,
            "why": self.why,
            "alignment_hotspot": self.alignment_hotspot,
            "mismatch_reasons": list(self.mismatch_reasons),
            "guidance_applied": self.guidance_applied,
            "softening_detected": self.softening_detected,
            "softening_signals": list(self.softening_signals),
            "effect_reason": self.effect_reason,
            "guidance_effective": self.guidance_effective,
            "response_score": round(float(self.response_score), 3),
            "goal_alignment_score": round(float(self.goal_alignment_score), 3),
            "tension_score_before": (
                round(float(self.tension_score_before), 3)
                if self.tension_score_before is not None
                else None
            ),
            "metadata": dict(self.metadata),
        }


@dataclass
class AlignmentMemoryMetrics:
    """Lightweight aggregate observability for alignment memory writes."""

    builder_calls: int = 0
    saved_total: int = 0
    skipped_total: int = 0
    save_errors: int = 0
    saved_because_hotspot: int = 0
    saved_because_softening: int = 0
    saved_because_guidance_effective: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "builder_calls": self.builder_calls,
            "saved_total": self.saved_total,
            "skipped_total": self.skipped_total,
            "save_errors": self.save_errors,
            "saved_because_hotspot": self.saved_because_hotspot,
            "saved_because_softening": self.saved_because_softening,
            "saved_because_guidance_effective": self.saved_because_guidance_effective,
        }


# ---------------------------------------------------------------------------
# Decision helpers (pure, deterministic)
# ---------------------------------------------------------------------------


def should_store_alignment_memory_unit(
    *,
    alignment_hotspot: str | None,
    mismatch_reasons: list[str],
    guidance_applied: bool,
    softening_detected: bool,
    guidance_effective: bool,
) -> bool:
    """Return True only when there is a meaningful alignment signal to store."""
    return bool(
        alignment_hotspot
        or mismatch_reasons
        or guidance_applied
        or softening_detected
        or guidance_effective
    )


# ---------------------------------------------------------------------------
# Builder (pure, never raises)
# ---------------------------------------------------------------------------


def build_alignment_memory_unit(
    item: dict,
    final_output: str,  # reserved for future metadata extraction
    alignment_outcome: dict,
) -> AlignmentMemoryUnit | None:
    """Build a compact memory unit from a completed pipeline item.

    Returns None when there is no question text or no outcome data.
    Never raises — the caller must handle None.
    """
    if not alignment_outcome:
        return None

    source_question = str(item.get("text") or item.get("input") or "").strip()
    if not source_question:
        return None

    # Alignment report (optional)
    report: dict = item.get("_alignment_report") or {}
    hotspot: str | None = None
    mismatch_reasons: list[str] = []
    if isinstance(report, dict):
        hotspots = report.get("pairwise_hotspots") or []
        if isinstance(hotspots, list) and hotspots:
            first = hotspots[0]
            if isinstance(first, dict):
                raw = first.get("tension_axis") or first.get("participants") or ""
                hotspot = str(raw) if raw else None
        raw_mismatch = report.get("mismatch_reasons") or []
        if isinstance(raw_mismatch, list):
            mismatch_reasons = [str(r) for r in raw_mismatch if r]

    # Intent
    intent_obj = item.get("_intent") or {}
    intent_str: str | None = None
    if isinstance(intent_obj, dict):
        raw_intent = intent_obj.get("type") or intent_obj.get("intent") or ""
        intent_str = str(raw_intent) if raw_intent else None
    elif isinstance(intent_obj, str):
        intent_str = intent_obj or None

    # WHY
    why_obj = item.get("_why") or {}
    why_str: str | None = None
    if isinstance(why_obj, dict):
        raw_why = why_obj.get("why") or why_obj.get("reason") or ""
        why_str = str(raw_why) if raw_why else None
    elif isinstance(why_obj, str):
        why_str = why_obj or None

    return AlignmentMemoryUnit(
        source_question=source_question,
        intent=intent_str,
        why=why_str,
        alignment_hotspot=hotspot,
        mismatch_reasons=mismatch_reasons,
        guidance_applied=bool(alignment_outcome.get("guidance_added")),
        softening_detected=bool(alignment_outcome.get("response_softened")),
        softening_signals=list(alignment_outcome.get("softening_signals") or []),
        effect_reason=alignment_outcome.get("effect_reason"),
        guidance_effective=bool(alignment_outcome.get("guidance_effective")),
        response_score=float(alignment_outcome.get("post_resonance_score") or 0.0),
        goal_alignment_score=float(alignment_outcome.get("post_goal_alignment_score") or 0.0),
        tension_score_before=(
            float(alignment_outcome.get("pre_tension_score") or 0.0) or None
        ),
        metadata={"cycle_id": str(item.get("_cycle_id") or "")},
    )


# ---------------------------------------------------------------------------
# JSONL persistence (best-effort, caller must catch)
# ---------------------------------------------------------------------------


def append_alignment_memory_unit(unit: AlignmentMemoryUnit, path: Path) -> None:
    """Append one unit to a JSONL file (append-only, no lock needed per line).

    Raises on I/O error — wrap in try/except at call site.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(unit.to_dict(), ensure_ascii=False) + "\n")
