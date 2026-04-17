from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .attachment_bond import AttachmentBond


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


class EmotionalBondingEvolutionEngine:
    """Deterministic long-term attachment evolution engine."""

    def evolve(
        self,
        bond: AttachmentBond,
        *,
        conversation_frequency: float = 0.0,
        conversation_quality: float = 0.0,
        user_feedback_signal: float = 0.0,
        omni_signal: dict[str, Any] | None = None,
        shared_relational_delta: float = 0.0,
        source: str = "care_cycle",
    ) -> AttachmentBond:
        omni = dict(omni_signal or {})
        tone = str(omni.get("tone") or "neutral").lower()
        fatigue = _clamp(float(omni.get("fatigue", 0.0) or 0.0))
        warmth_boost = 0.03 if tone in {"warm", "supportive", "joyful"} else 0.0

        base_delta = (
            0.25 * _clamp(conversation_frequency)
            + 0.35 * _clamp(conversation_quality)
            + 0.2 * _clamp(user_feedback_signal)
            + 0.2 * _clamp(shared_relational_delta)
            + warmth_boost
            - 0.25 * fatigue
            - 0.5
        )
        delta = max(-0.1, min(0.1, base_delta))

        old_strength = float(bond.attachment_strength or 0.0)
        bond.attachment_strength = round(_clamp(old_strength + delta), 4)
        stability_shift = 0.03 if abs(delta) < 0.04 else -0.02
        bond.attachment_stability = round(_clamp(bond.attachment_stability + stability_shift), 4)
        bond.attachment_style = self._derive_style(bond.attachment_strength, bond.attachment_stability)

        vector = list(bond.emotional_history_vector or [])
        vector.extend([
            round(_clamp(conversation_frequency), 4),
            round(_clamp(conversation_quality), 4),
            round(_clamp(user_feedback_signal), 4),
            round(_clamp(1.0 - fatigue), 4),
            round(bond.attachment_strength, 4),
        ])
        bond.emotional_history_vector = vector[-64:]
        bond.updated_at = _utc_now()

        if bond.attachment_strength >= 0.8 and old_strength < 0.8:
            bond.bonding_milestones.append(
                {
                    "timestamp": bond.updated_at,
                    "type": "deep_trust",
                    "summary": "Attachment strength crossed deep-trust threshold.",
                    "source": source,
                }
            )

        if bond.attachment_strength < 0.4:
            bond.repair_actions.append(
                {
                    "timestamp": bond.updated_at,
                    "action": "attachment_repair_prompt",
                    "reason": "attachment_strength_low",
                    "suggested_tone": "gentle_reconnect",
                }
            )

        bond.audit_log.append(
            {
                "timestamp": bond.updated_at,
                "event": "attachment_evolved",
                "source": source,
                "old_strength": round(old_strength, 4),
                "new_strength": round(bond.attachment_strength, 4),
                "delta": round(delta, 4),
                "style": bond.attachment_style,
            }
        )
        bond.audit_log = bond.audit_log[-500:]
        bond.bonding_milestones = bond.bonding_milestones[-200:]
        bond.repair_actions = bond.repair_actions[-200:]
        return bond

    def reset_attachment(self, bond: AttachmentBond, *, reason: str = "soft_reset") -> AttachmentBond:
        now = _utc_now()
        bond.audit_log.append(
            {
                "timestamp": now,
                "event": "attachment_soft_reset",
                "reason": str(reason or "soft_reset"),
                "old_strength": round(float(bond.attachment_strength or 0.0), 4),
            }
        )
        bond.attachment_strength = 0.15
        bond.attachment_stability = 0.35
        bond.attachment_style = "secure"
        bond.emotional_history_vector = []
        bond.updated_at = now
        return bond

    def build_insight(
        self,
        *,
        bond: AttachmentBond,
        arc: list[dict[str, Any]],
        window: int = 60,
    ) -> dict[str, Any]:
        points = list(arc or [])[-max(2, int(window or 2)):]
        delta = 0.0
        if len(points) >= 2:
            delta = float(points[-1].get("attachment_strength", bond.attachment_strength) or 0.0) - float(
                points[0].get("attachment_strength", bond.attachment_strength) or 0.0
            )
        top_milestone = (bond.bonding_milestones or [{}])[-1]
        return {
            "attachment_strength": round(float(bond.attachment_strength or 0.0), 4),
            "attachment_style": str(bond.attachment_style or "secure"),
            "attachment_stability": round(float(bond.attachment_stability or 0.0), 4),
            "window_points": len(points),
            "strength_delta": round(delta, 4),
            "top_milestone": top_milestone,
            "repair_actions_pending": len(bond.repair_actions),
        }

    @staticmethod
    def _derive_style(strength: float, stability: float) -> str:
        if strength >= 0.75 and stability >= 0.55:
            return "secure"
        if strength >= 0.65 and stability < 0.45:
            return "anxious"
        if strength < 0.45 and stability >= 0.6:
            return "avoidant"
        if strength < 0.45 and stability < 0.45:
            return "disorganized"
        return "secure"
