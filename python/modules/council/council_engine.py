from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from modules.graph.models import RelationalSelf
from modules.council.self_constitution import RelationalSelfConstitution
from modules.shared.event_bus import EventBus


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RelationalBreach:
    breach: bool
    threshold: float
    coherence_score: float
    reason: str


class RelationalCouncilEngine:
    """Council over holistic RelationalSelf instead of isolated units."""

    def __init__(
        self,
        *,
        coherence_guard_threshold: float = 0.4,
        event_bus: EventBus | None = None,
    ) -> None:
        self.coherence_guard_threshold = float(coherence_guard_threshold)
        self.constitution = RelationalSelfConstitution()
        self.event_bus = event_bus
        self._live_sessions: dict[str, dict[str, Any]] = {}

    def run_mode(self, *, mode: str, relational_self: RelationalSelf) -> dict[str, Any]:
        normalized_mode = str(mode or "self-consistency-check").strip().lower()
        if normalized_mode == "self-consistency-check":
            return self._consistency_check(relational_self)
        if normalized_mode == "self-evolution-proposal":
            return self._evolution_proposal(relational_self)
        if normalized_mode == "self-preservation":
            return self._self_preservation(relational_self)
        if normalized_mode == "multi-user-live":
            return self._multi_user_live(relational_self)
        return {
            "mode": normalized_mode,
            "accepted": False,
            "reason": "unsupported_mode",
        }

    def join_live_council(self, *, session_id: str, participant_id: str, consent: bool) -> dict[str, Any]:
        sid = str(session_id or "").strip()
        pid = str(participant_id or "").strip()
        if not sid or not pid:
            return {"joined": False, "reason": "invalid_session_or_participant", "session_id": sid}
        session = self._live_sessions.setdefault(
            sid,
            {
                "session_id": sid,
                "mode": "multi-user-live",
                "status": "active",
                "participants": {},
                "started_at": _utc_now(),
                "updated_at": _utc_now(),
                "audit_log": [],
            },
        )
        if not consent:
            event = {
                "type": "council.live.join_denied",
                "session_id": sid,
                "participant_id": pid,
                "consent": False,
                "timestamp": _utc_now(),
            }
            session["audit_log"].append(event)
            self._broadcast(event)
            return {"joined": False, "reason": "consent_required", "session_id": sid}
        session["participants"][pid] = {"participant_id": pid, "consent": True, "joined_at": _utc_now()}
        session["updated_at"] = _utc_now()
        event = {
            "type": "council.live.participant_joined",
            "session_id": sid,
            "participant_id": pid,
            "consent": True,
            "timestamp": _utc_now(),
        }
        session["audit_log"].append(event)
        self._broadcast(event)
        return {
            "joined": True,
            "session_id": sid,
            "participant_id": pid,
            "participant_count": len(session["participants"]),
        }

    def leave_live_council(self, *, session_id: str, participant_id: str) -> dict[str, Any]:
        sid = str(session_id or "").strip()
        pid = str(participant_id or "").strip()
        session = self._live_sessions.get(sid)
        if not session:
            return {"left": False, "reason": "session_not_found", "session_id": sid}
        session["participants"].pop(pid, None)
        session["updated_at"] = _utc_now()
        event = {
            "type": "council.live.participant_left",
            "session_id": sid,
            "participant_id": pid,
            "timestamp": _utc_now(),
        }
        session["audit_log"].append(event)
        if not session["participants"]:
            session["status"] = "completed"
        self._broadcast(event)
        return {"left": True, "session_id": sid, "participant_count": len(session["participants"])}

    def get_live_council_state(self, *, session_id: str) -> dict[str, Any]:
        session = self._live_sessions.get(str(session_id or "").strip())
        if not session:
            return {
                "resource": "council/live",
                "mode": "multi-user-live",
                "status": "idle",
                "session_id": session_id,
                "participants": [],
                "shared_emotional_summary": {},
                "audit_log": [],
            }
        return {
            "resource": "council/live",
            "mode": "multi-user-live",
            "status": session.get("status", "active"),
            "session_id": session.get("session_id"),
            "participants": list(session.get("participants", {}).values()),
            "shared_emotional_summary": dict(session.get("shared_emotional_summary", {})),
            "audit_log": list(session.get("audit_log", [])),
            "updated_at": session.get("updated_at"),
        }

    def weighted_vote(
        self,
        *,
        proposal_id: str,
        votes: list[dict[str, Any]],
        reputation_weights: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Compute weighted vote outcome for multi-user council proposals."""
        weighted_yes = 0.0
        weighted_no = 0.0
        weight_map = {str(k): float(v) for k, v in dict(reputation_weights or {}).items()}
        normalized_votes: list[dict[str, Any]] = []
        for row in list(votes or []):
            participant_id = str(row.get("participant_id") or "").strip()
            if not participant_id:
                continue
            choice = str(row.get("vote") or "abstain").strip().lower()
            if choice not in {"yes", "no", "abstain"}:
                choice = "abstain"
            weight = max(0.05, min(2.0, float(weight_map.get(participant_id, 1.0))))
            if choice == "yes":
                weighted_yes += weight
            elif choice == "no":
                weighted_no += weight
            normalized_votes.append(
                {
                    "participant_id": participant_id,
                    "vote": choice,
                    "weight": weight,
                }
            )
        accepted = weighted_yes > weighted_no
        return {
            "proposal_id": str(proposal_id or ""),
            "accepted": accepted,
            "weighted_yes": round(weighted_yes, 4),
            "weighted_no": round(weighted_no, 4),
            "quorum": len(normalized_votes),
            "votes": normalized_votes,
            "decision_mode": "weighted_reputation_voting",
            "timestamp": _utc_now(),
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
        actions: list[dict[str, Any]] = []
        if float(relational_self.self_coherence_score or 0.0) < 0.7:
            proposals.append({
                "type": "strengthen_reinforcing_edges",
                "impact": "raise_coherence",
            })
            actions.append(
                {
                    "action": "increase_reinforcing_edge_strength",
                    "params": {"max_delta": 0.05, "target_relation_type": "reinforces"},
                }
            )
        if len(relational_self.core_nodes) < 3:
            proposals.append({
                "type": "expand_core_memory",
                "impact": "increase_identity_stability",
            })
            actions.append(
                {
                    "action": "expand_core_nodes_window",
                    "params": {"recent_window_increment": 5},
                }
            )
        return {
            "mode": "self-evolution-proposal",
            "proposal_count": len(proposals),
            "proposals": proposals,
            "actions": actions,
        }

    def _self_preservation(self, relational_self: RelationalSelf) -> dict[str, Any]:
        breach = self.detect_breach(relational_self)
        constitution = self.constitution.evaluate(relational_self)
        blocked = breach.breach or (not constitution.passed)

        # Phase 2.4: include emotional snapshot as informational context only.
        # Constitution / policy gate outcome is NOT altered by emotional state.
        emotional_snapshot: dict[str, Any] = {}
        emotional_summary = dict(relational_self.emotional_summary or {})
        if emotional_summary:
            emotional_snapshot = {
                "dominant_tone": emotional_summary.get("dominant_tone", "neutral"),
                "bond_strength": emotional_summary.get("bond_strength", 0.0),
                "bond_trend": emotional_summary.get("bond_trend", "stable"),
                "confidence": emotional_summary.get("confidence", 0.0),
                # Explicit reminder: emotional state does not override constitution
                "constitution_override": False,
            }

        return {
            "mode": "self-preservation",
            "blocked": blocked,
            "reason": breach.reason if breach.breach else ("constitution_violation" if not constitution.passed else "stable"),
            "coherence_score": breach.coherence_score,
            "threshold": breach.threshold,
            "constitution": constitution.to_dict(),
            # Informational only — no gate authority
            "emotional_context": emotional_snapshot,
            "attachment_behavior": self._attachment_behavior(relational_self),
        }

    def _multi_user_live(self, relational_self: RelationalSelf) -> dict[str, Any]:
        attachment_behavior = self._attachment_behavior(relational_self)
        shared_summary = {
            "dominant_tone": relational_self.last_emotional_state or "neutral",
            "bond_strength": float(relational_self.bond_strength or 0.0),
            "emotional_decay": float(relational_self.emotional_decay or 1.0),
            "attachment_strength": float(relational_self.attachment_strength or 0.0),
            "attachment_style": str(relational_self.attachment_style or "secure"),
            "attachment_stability": float(relational_self.attachment_stability or 0.5),
            "attachment_behavior": attachment_behavior,
            "message": "Shared emotional state synchronized in real time.",
        }
        event = {
            "type": "council.live.shared_state_updated",
            "summary": shared_summary,
            "timestamp": _utc_now(),
        }
        self._broadcast(event)
        return {
            "mode": "multi-user-live",
            "accepted": True,
            "shared_emotional_summary": shared_summary,
            "real_time_sync": True,
        }

    def _attachment_behavior(self, relational_self: RelationalSelf) -> dict[str, Any]:
        strength = float(relational_self.attachment_strength or 0.0)
        style = str(relational_self.attachment_style or "secure")
        if strength >= 0.75:
            tone = "warm_proactive"
            initiative = "high"
            repair_actions: list[str] = []
        elif strength >= 0.45:
            tone = "balanced_supportive"
            initiative = "medium"
            repair_actions = ["check_alignment", "invite_reflection"]
        else:
            tone = "careful_reconnect"
            initiative = "low"
            repair_actions = ["ask_repair_question", "offer_small_next_step"]
        return {
            "attachment_strength": round(strength, 4),
            "attachment_style": style,
            "tone_policy": tone,
            "initiative_level": initiative,
            "repair_actions": repair_actions,
        }

    def _broadcast(self, event_payload: dict[str, Any]) -> None:
        if self.event_bus is None:
            return
        self.event_bus.publish(type("Event", (), event_payload)())
