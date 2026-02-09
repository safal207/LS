from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List
import uuid


@dataclass(frozen=True)
class MeshEnvelope:
    message_type: str
    origin: str
    destination: str
    payload: Dict[str, Any]
    hops: List[str] = field(default_factory=list)
    envelope_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mesh": "1.0",
            "id": self.envelope_id,
            "type": self.message_type,
            "origin": self.origin,
            "destination": self.destination,
            "payload": self.payload,
            "hops": list(self.hops),
            "created_at": self.created_at,
        }

    def with_hop(self, peer_id: str) -> "MeshEnvelope":
        return MeshEnvelope(
            message_type=self.message_type,
            origin=self.origin,
            destination=self.destination,
            payload=self.payload,
            hops=[*self.hops, peer_id],
            envelope_id=self.envelope_id,
            created_at=self.created_at,
        )
