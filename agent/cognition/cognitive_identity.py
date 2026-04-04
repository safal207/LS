from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List
import uuid


@dataclass(frozen=True)
class CognitiveIdentity:
    """Portable identity profile for cross-agent cognitive federation."""

    agent_id: str
    public_key: str
    creator: str = "LS"
    capabilities: List[str] = field(default_factory=list)
    reputation_score: float = 0.5

    @staticmethod
    def create(
        creator: str = "LS",
        capabilities: List[str] | None = None,
        public_key: str = "ed25519:local",
    ) -> "CognitiveIdentity":
        return CognitiveIdentity(
            agent_id=f"did:agent:{uuid.uuid4()}",
            public_key=public_key,
            creator=creator,
            capabilities=list(capabilities or []),
            reputation_score=0.5,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "public_key": self.public_key,
            "creator": self.creator,
            "capabilities": list(self.capabilities),
            "reputation_score": float(self.reputation_score),
        }

    @staticmethod
    def from_dict(payload: Dict[str, Any]) -> "CognitiveIdentity":
        return CognitiveIdentity(
            agent_id=str(payload.get("agent_id") or f"did:agent:{uuid.uuid4()}"),
            public_key=str(payload.get("public_key") or "ed25519:local"),
            creator=str(payload.get("creator") or "LS"),
            capabilities=[str(item) for item in payload.get("capabilities", [])],
            reputation_score=float(payload.get("reputation_score", 0.5)),
        )
