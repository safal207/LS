from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict
import json
import uuid


LIP_VERSION = "1.0"


@dataclass(frozen=True)
class LipIdentity:
    agent_id: str
    fingerprint: str

    def as_dict(self) -> Dict[str, Any]:
        return {"agent_id": self.agent_id, "fingerprint": self.fingerprint}


@dataclass(frozen=True)
class LipSource:
    uri: str
    trust_tier: str
    retrieved_at: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "trust_tier": self.trust_tier,
            "retrieved_at": self.retrieved_at,
        }


def canonical_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_envelope(
    message_type: str,
    sender: LipIdentity,
    receiver: LipIdentity,
    payload: Dict[str, Any],
    source: LipSource,
) -> Dict[str, Any]:
    return {
        "lip": LIP_VERSION,
        "msg_id": str(uuid.uuid4()),
        "type": message_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sender": sender.as_dict(),
        "receiver": receiver.as_dict(),
        "source": source.as_dict(),
        "payload": payload,
    }


def validate_envelope(envelope: Dict[str, Any]) -> None:
    required = ["lip", "msg_id", "type", "timestamp", "sender", "receiver", "source", "payload"]
    missing = [key for key in required if key not in envelope]
    if missing:
        raise ValueError(f"Missing envelope fields: {', '.join(missing)}")
    if envelope["lip"] != LIP_VERSION:
        raise ValueError("Unsupported LIP version")
    if not isinstance(envelope["payload"], dict):
        raise ValueError("Payload must be an object")
    if not isinstance(envelope.get("source"), dict):
        raise ValueError("Missing source block")
    for section in ("sender", "receiver"):
        identity = envelope.get(section)
        if not isinstance(identity, dict) or "agent_id" not in identity or "fingerprint" not in identity:
            raise ValueError("Sender/receiver missing identity fields")


def signable_payload(envelope: Dict[str, Any]) -> str:
    data = dict(envelope)
    data.pop("sign", None)
    return canonical_json(data)
