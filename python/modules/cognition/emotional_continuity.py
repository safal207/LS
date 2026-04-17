# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from modules.cognition.emotional_memory import EmotionalBondingEngine


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EmotionalContinuityState:
    last_emotional_state: str = "neutral"
    bond_strength: float = 0.0
    emotional_decay: float = 1.0
    emotional_half_life_hours: float = 72.0
    last_updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_emotional_state": self.last_emotional_state,
            "bond_strength": float(max(0.0, min(1.0, self.bond_strength))),
            "emotional_decay": float(max(0.05, min(1.0, self.emotional_decay))),
            "emotional_half_life_hours": float(max(0.001, self.emotional_half_life_hours)),
            "last_updated_at": self.last_updated_at or _utc_now(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EmotionalContinuityState":
        return cls(
            last_emotional_state=str(payload.get("last_emotional_state") or "neutral"),
            bond_strength=float(payload.get("bond_strength", 0.0) or 0.0),
            emotional_decay=float(payload.get("emotional_decay", 1.0) if payload.get("emotional_decay") is not None else 1.0),
            emotional_half_life_hours=float(payload.get("emotional_half_life_hours", 72.0) or 72.0),
            last_updated_at=payload.get("last_updated_at"),
        )


class EmotionalContinuityEngine:
    """Computes and refreshes persistent emotional continuity state."""

    def __init__(self) -> None:
        self._bonding = EmotionalBondingEngine()

    def refresh(
        self,
        *,
        entries: list[dict[str, Any]],
        fallback_bond: float = 0.0,
        fallback_tone: str = "neutral",
    ) -> EmotionalContinuityState:
        if not entries:
            return EmotionalContinuityState(
                last_emotional_state=fallback_tone,
                bond_strength=float(max(0.0, min(1.0, fallback_bond))),
                emotional_decay=1.0,
                emotional_half_life_hours=72.0,
                last_updated_at=_utc_now(),
            )

        latest = dict(entries[-1])
        half_life = float(latest.get("emotional_half_life_hours", 72.0) or 72.0)
        decay = self._bonding.compute_temporal_decay(
            str(latest.get("timestamp") or _utc_now()),
            half_life_hours=half_life,
        )
        return EmotionalContinuityState(
            last_emotional_state=str(latest.get("emotional_tone") or fallback_tone),
            bond_strength=float(latest.get("bond_strength", fallback_bond) or fallback_bond),
            emotional_decay=float(decay),
            emotional_half_life_hours=half_life,
            last_updated_at=str(latest.get("timestamp") or _utc_now()),
        )
