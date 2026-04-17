from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

_VALID_ATTACHMENT_STYLES = {"secure", "anxious", "avoidant", "disorganized"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


@dataclass
class AttachmentBond:
    """Long-term relational attachment snapshot.

    Metrics are inferred from observed interaction patterns; they do not
    represent claims of subjective consciousness.
    """

    bond_id: str = field(default_factory=lambda: str(uuid4()))
    schema_version: str = "1.0"
    updated_at: str = field(default_factory=_utc_now)
    attachment_strength: float = 0.0
    attachment_style: str = "secure"
    emotional_history_vector: list[float] = field(default_factory=list)
    attachment_stability: float = 0.5
    bonding_milestones: list[dict[str, Any]] = field(default_factory=list)
    repair_actions: list[dict[str, Any]] = field(default_factory=list)
    audit_log: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.attachment_strength = _clamp(self.attachment_strength)
        self.attachment_stability = _clamp(self.attachment_stability)
        style = str(self.attachment_style or "secure").strip().lower()
        if style not in _VALID_ATTACHMENT_STYLES:
            style = "secure"
        self.attachment_style = style
        self.emotional_history_vector = [float(v) for v in list(self.emotional_history_vector or [])]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AttachmentBond":
        return cls(
            bond_id=str(data.get("bond_id") or str(uuid4())),
            schema_version=str(data.get("schema_version") or "1.0"),
            updated_at=str(data.get("updated_at") or _utc_now()),
            attachment_strength=float(data.get("attachment_strength", 0.0) or 0.0),
            attachment_style=str(data.get("attachment_style") or "secure"),
            emotional_history_vector=list(data.get("emotional_history_vector") or []),
            attachment_stability=float(data.get("attachment_stability", 0.5) or 0.5),
            bonding_milestones=list(data.get("bonding_milestones") or []),
            repair_actions=list(data.get("repair_actions") or []),
            audit_log=list(data.get("audit_log") or []),
            metadata=dict(data.get("metadata") or {}),
        )
