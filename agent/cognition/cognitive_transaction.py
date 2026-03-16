from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict
import uuid


SUPPORTED_ACTIONS = {
    "approve_proposal",
    "reject_proposal",
    "edit_proposal",
    "detect_contradiction",
    "belief_update",
    "canonical_update",
    "reflection_generated",
    "code_commit",
}


@dataclass(frozen=True)
class CognitiveTransaction:
    tx_id: str
    timestamp: str
    actor: str
    action: str
    payload: Dict[str, Any]

    @staticmethod
    def create(actor: str, action: str, payload: Dict[str, Any]) -> "CognitiveTransaction":
        if action not in SUPPORTED_ACTIONS:
            raise ValueError(f"unsupported cognitive action: {action}")
        return CognitiveTransaction(
            tx_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            actor=actor,
            action=action,
            payload=payload,
        )
