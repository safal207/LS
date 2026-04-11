from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from modules.graph.models import RelationalSelf


@dataclass
class RelationalBreach:
    breach: bool
    threshold: float
    coherence_score: float
    reason: str


class RelationalCouncilEngine:
    """Council over holistic RelationalSelf instead of isolated units."""

    def __init__(self, *, coherence_guard_threshold: float = 0.4) -> None:
        self.coherence_guard_threshold = float(coherence_guard_threshold)

    def run_mode(self, *, mode: str, relational_self: RelationalSelf) -> dict[str, Any]:
        normalized_mode = str(mode or "self-consistency-check").strip().lower()
        if normalized_mode == "self-consistency-check":
            return self._consistency_check(relational_self)
        if normalized_mode == "self-evolution-proposal":
            return self._evolution_proposal(relational_self)
        if normalized_mode == "self-preservation":
            return self._self_preservation(relational_self)
        return {
            "mode": normalized_mode,
            "accepted": False,
            "reason": "unsupported_mode",
        }

    def detect_breach(self, relational_self: RelationalSelf) -> RelationalBreach:
        coherence = float(relational_self.self_coherence_score or 0.0)
        is_breach = coherence < self.coherence_guard_threshold
        return RelationalBreach(
            breach=is_breach,
            threshold=self.coherence_guard_threshold,
            coherence_score=coherence,
            reason="coherence_below_threshold" if is_breach else "stable",
        )

    def _consistency_check(self, relational_self: RelationalSelf) -> dict[str, Any]:
        contradictions = [
            edge
            for edge in relational_self.core_edges
            if str(edge.get("relation_type") or "") == "contradicts"
            and float(edge.get("strength", 0.0) or 0.0) >= 0.7
        ]
        return {
            "mode": "self-consistency-check",
            "contradiction_count": len(contradictions),
            "ok": len(contradictions) == 0,
            "coherence_score": float(relational_self.self_coherence_score or 0.0),
        }

    def _evolution_proposal(self, relational_self: RelationalSelf) -> dict[str, Any]:
        proposals: list[dict[str, Any]] = []
        if float(relational_self.self_coherence_score or 0.0) < 0.7:
            proposals.append({
                "type": "strengthen_reinforcing_edges",
                "impact": "raise_coherence",
            })
        if len(relational_self.core_nodes) < 3:
            proposals.append({
                "type": "expand_core_memory",
                "impact": "increase_identity_stability",
            })
        return {
            "mode": "self-evolution-proposal",
            "proposal_count": len(proposals),
            "proposals": proposals,
        }

    def _self_preservation(self, relational_self: RelationalSelf) -> dict[str, Any]:
        breach = self.detect_breach(relational_self)
        return {
            "mode": "self-preservation",
            "blocked": breach.breach,
            "reason": breach.reason,
            "coherence_score": breach.coherence_score,
            "threshold": breach.threshold,
        }
