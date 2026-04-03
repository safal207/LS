# -*- coding: utf-8 -*-
"""Relational Tension Layer — psychological depth for interaction analysis.

Builds on top of RelationalFieldAnalyzer to produce TensionObservation:
a structured psychological read of an interaction that captures not just
what is expressed (surface), but what underlies it (background pressure,
unmet need, projection direction) and what could help (repair strategy).

Structure::

    surface_intent      — what is expressed / visible action
    background_pressure — underlying state (fear, overload, hurt, urgency…)
    unmet_need          — the real need not being addressed
    projection_direction — where tension is directed ("other", "self",
                           "situation", "system")
    tension_score       — 0–1 intensity (from field analyzer)
    alignment_gap       — tension_score − alignment_score (surface vs reality)
    repair_strategy     — suggested approach to reduce the gap

Scopes supported:
    human-human   — interpersonal dynamics
    human-agent   — user ↔ AI system
    agent-agent   — multi-agent coordination

No LLM calls, no routing changes, no external I/O.  Pure heuristic.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from .models import RelationalFieldSnapshot
from .relational_field import RelationalFieldAnalyzer


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

# background_pressure tag → unmet_need
_NEED_MAP: dict[str, str] = {
    "fear":         "safety",
    "overload":     "relief_and_support",
    "urgency":      "clear_timeline",
    "hurt":         "recognition",
    "uncertainty":  "clarity_and_guidance",
    "control_loss": "restored_agency",
}

# foreground_expression tag → surface_intent label
_INTENT_MAP: dict[str, str] = {
    "attack":         "blame",
    "withdrawal":     "disengage",
    "defensiveness":  "defend",
    "pressure":       "demand",
    "appeal":         "request_help",
    "repair_attempt": "reconnect",
}

# foreground_expression tag → projection_direction
_PROJECTION_MAP: dict[str, str] = {
    "attack":         "other",
    "withdrawal":     "self",
    "defensiveness":  "self",
    "pressure":       "other",
    "appeal":         "system",
    "repair_attempt": "other",
}

# (dominant_signal, first_background, first_foreground) → repair_strategy
# Checked left-to-right; first match wins.
_REPAIR_RULES: list[tuple[tuple[str, str, str], str]] = [
    (("tension",   "fear",         "attack"),        "acknowledge_safety_before_content"),
    (("tension",   "fear",         "pressure"),      "slow_down_and_validate"),
    (("tension",   "hurt",         "attack"),        "name_the_hurt_not_the_blame"),
    (("tension",   "overload",     "pressure"),      "reduce_load_offer_options"),
    (("tension",   "overload",     "withdrawal"),    "reduce_load_offer_options"),
    (("tension",   "urgency",      "pressure"),      "clarify_timeline_together"),
    (("tension",   "control_loss", "attack"),        "restore_agency_and_choice"),
    (("tension",   "uncertainty",  "defensiveness"), "provide_clarity_no_judgment"),
    (("tension",   "*",            "*"),             "de_escalate_and_reflect"),
    (("alignment", "*",            "appeal"),        "co_create_solution"),
    (("alignment", "*",            "repair_attempt"),"affirm_and_build"),
    (("alignment", "*",            "*"),             "deepen_connection"),
    (("*",         "*",            "appeal"),        "respond_to_need_directly"),
    (("*",         "*",            "repair_attempt"),"affirm_repair_attempt"),
    (("*",         "*",            "*"),             "observe_and_hold_space"),
]


def _match_repair(dominant: str, background: list[str], foreground: list[str]) -> str:
    # Compound dominants ("foreground:X", "background:X") are treated as
    # "tension" when background pressure is present, otherwise as "neutral".
    if dominant.startswith("foreground:") or dominant.startswith("background:"):
        effective_dominant = "tension" if background else "neutral"
    else:
        effective_dominant = dominant

    bg0 = background[0] if background else "*"
    fg0 = foreground[0] if foreground else "*"
    for (d, b, f), strategy in _REPAIR_RULES:
        d_ok = d == "*" or d == effective_dominant
        b_ok = b == "*" or b == bg0
        f_ok = f == "*" or f == fg0
        if d_ok and b_ok and f_ok:
            return strategy
    return "observe_and_hold_space"


# ---------------------------------------------------------------------------
# TensionObservation dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TensionObservation:
    """Structured psychological read of one interaction moment.

    Attributes:
        observation_id:      Unique identifier.
        timestamp:           UTC ISO-8601 capture time.
        participants:        Identifiers of the parties involved.
        interaction_scope:   "human-human", "human-agent", or "agent-agent".
        surface_intent:      Visible expressed action or attitude.
        background_pressure: Detected underlying states (fear, overload…).
        unmet_need:          The core need not being addressed, or None.
        projection_direction: Who/what the tension is aimed at.
        tension_score:       0–1 intensity.
        alignment_gap:       tension_score − alignment_score; positive means
                             the surface is more conflicted than cooperative.
        repair_strategy:     Suggested approach to reduce the gap.
        source_snapshot_id:  Optional link to the originating
                             RelationalFieldSnapshot.
        metadata:            Arbitrary extra context.
    """

    observation_id: str
    timestamp: str
    participants: list[str]
    interaction_scope: str
    surface_intent: str
    background_pressure: list[str]
    unmet_need: Optional[str]
    projection_direction: str
    tension_score: float
    alignment_gap: float
    repair_strategy: str
    source_snapshot_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TensionObservation":
        return cls(
            observation_id=str(data.get("observation_id") or str(uuid4())),
            timestamp=str(data.get("timestamp") or _utc_now()),
            participants=list(data.get("participants") or []),
            interaction_scope=str(data.get("interaction_scope") or "human-human"),
            surface_intent=str(data.get("surface_intent") or "observe"),
            background_pressure=list(data.get("background_pressure") or []),
            unmet_need=data.get("unmet_need"),
            projection_direction=str(data.get("projection_direction") or "unknown"),
            tension_score=float(data.get("tension_score", 0.0) or 0.0),
            alignment_gap=float(data.get("alignment_gap", 0.0) or 0.0),
            repair_strategy=str(data.get("repair_strategy") or "observe_and_hold_space"),
            source_snapshot_id=data.get("source_snapshot_id"),
            metadata=dict(data.get("metadata") or {}),
        )


# ---------------------------------------------------------------------------
# TensionAnalyzer
# ---------------------------------------------------------------------------


class TensionAnalyzer:
    """Produces TensionObservation by layering psychological inference on top
    of RelationalFieldAnalyzer's signal detection.

    Usage::

        analyzer = TensionAnalyzer()
        obs = analyzer.observe(
            text="Ты опять это сделал! Я так устала...",
            participants=["alice", "bob"],
            interaction_scope="human-human",
        )
        print(obs.repair_strategy)   # e.g. "name_the_hurt_not_the_blame"

    The analyzer is stateless — each call is independent.
    """

    def __init__(
        self,
        field_analyzer: Optional[RelationalFieldAnalyzer] = None,
        graph_store: Any = None,
    ) -> None:
        self._fa = field_analyzer or RelationalFieldAnalyzer()
        self._graph_store = graph_store  # duck-typed: needs store_relational_snapshot()

    def observe(
        self,
        *,
        text: str,
        participants: list[str] | None = None,
        interaction_scope: str = "human-human",
        context: dict[str, Any] | None = None,
        graph_store: Any = None,
    ) -> TensionObservation:
        """Analyze *text* and return a TensionObservation.

        Args:
            text:              The raw interaction text to analyze.
            participants:      Identifiers of the parties (names, IDs…).
            interaction_scope: One of "human-human", "human-agent",
                               "agent-agent".  Default: "human-human".
            context:           Optional extra dict stored in metadata.
            graph_store:       Optional store instance (duck-typed).  When
                               provided, the underlying RelationalFieldSnapshot
                               is persisted via ``store_relational_snapshot()``.
                               Failures are best-effort (logged, not raised).

        Returns:
            A frozen TensionObservation.
        """
        snap: RelationalFieldSnapshot = self._fa.analyze(
            text=text,
            participants=participants,
            interaction_scope=interaction_scope,
            context=context,
        )

        # Persist the base snapshot if a store is available (best-effort).
        active_store = graph_store if graph_store is not None else self._graph_store
        if active_store is not None:
            try:
                active_store.store_relational_snapshot(snap)
            except Exception as exc:
                import logging as _logging
                _logging.getLogger(__name__).debug(
                    "TensionAnalyzer snapshot store skipped: %s", exc
                )

        foreground = list(snap.foreground_expression)
        background = list(snap.background_pressure)
        dominant = str(snap.dominant_signal)

        surface_intent = self._infer_surface_intent(foreground)
        unmet_need = self._infer_unmet_need(background)
        projection = self._infer_projection(foreground, interaction_scope)
        alignment_gap = round(
            max(-1.0, min(1.0, snap.tension_score - snap.alignment_score)),
            3,
        )
        repair = _match_repair(dominant, background, foreground)

        return TensionObservation(
            observation_id=str(uuid4()),
            timestamp=snap.timestamp,
            participants=list(snap.participants),
            interaction_scope=snap.interaction_scope,
            surface_intent=surface_intent,
            background_pressure=background,
            unmet_need=unmet_need,
            projection_direction=projection,
            tension_score=round(snap.tension_score, 3),
            alignment_gap=alignment_gap,
            repair_strategy=repair,
            source_snapshot_id=snap.field_id,
            metadata={
                "alignment_score": snap.alignment_score,
                "dominant_signal": dominant,
                "text_length": len(str(text or "")),
                "context": dict(context or {}),
            },
        )

    # ------------------------------------------------------------------
    # Inference helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_surface_intent(foreground: list[str]) -> str:
        for tag in foreground:
            if tag in _INTENT_MAP:
                return _INTENT_MAP[tag]
        return "observe"

    @staticmethod
    def _infer_unmet_need(background: list[str]) -> Optional[str]:
        for tag in background:
            if tag in _NEED_MAP:
                return _NEED_MAP[tag]
        return None

    @staticmethod
    def _infer_projection(foreground: list[str], scope: str) -> str:
        for tag in foreground:
            if tag in _PROJECTION_MAP:
                proj = _PROJECTION_MAP[tag]
                # In agent scopes "appeal" projects onto the agent, not system
                if proj == "system" and scope == "human-agent":
                    return "agent"
                return proj
        # Neutral: project onto the broader situation
        return "situation"
