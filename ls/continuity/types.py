from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

ContinuityStatus = Literal["intact", "uncertain", "ruptured", "repaired"]
HallucinationRisk = Literal["none", "low", "medium", "high"]
GovernanceDecision = Literal[
    "continue",
    "validate_context",
    "repair_before_continue",
    "hold_until_context",
    "human_review",
]


@dataclass(frozen=True)
class ContinuityInput:
    """Input for a deterministic session-continuity check."""

    prompt: str
    raw_output: str
    session_id: str = "session_default"
    agent_id: str = "agent_default"
    agent_type: str = "other"
    available_context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ContinuityEvent:
    """Session-continuity event compatible with session-continuity-event.v0.1."""

    schema_version: str
    event_id: str
    session_id: str
    agent_id: str
    agent_type: str
    expected_session_type: str
    actual_response_type: str
    continuity_status: ContinuityStatus
    rupture_detected: bool
    rupture_type: str
    last_shared_point: str
    missing_context: list[str]
    inferred_story: str
    hallucination_risk: HallucinationRisk
    repair_prompt: str
    next_safe_action: GovernanceDecision
    governance_decision: GovernanceDecision
    evidence: list[dict[str, Any]]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def new_event_id(prefix: str = "sce") -> str:
    return f"{prefix}_{uuid4().hex}"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
