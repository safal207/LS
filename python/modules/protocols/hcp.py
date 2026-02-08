from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable
import json
import uuid


HCP_VERSION = "1.0"


@dataclass(frozen=True)
class HcpIdentity:
    agent_id: str
    fingerprint: str

    def as_dict(self) -> Dict[str, Any]:
        return {"agent_id": self.agent_id, "fingerprint": self.fingerprint}


@dataclass(frozen=True)
class HcpHumanState:
    presence: str
    affect: str
    clarity: int
    pressure: int
    intent: str
    consent: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "presence": self.presence,
            "affect": self.affect,
            "clarity": self.clarity,
            "pressure": self.pressure,
            "intent": self.intent,
            "consent": self.consent,
        }


def canonical_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_envelope(
    message_type: str,
    sender: HcpIdentity,
    receiver: HcpIdentity,
    payload: Dict[str, Any],
    human_state: HcpHumanState,
) -> Dict[str, Any]:
    return {
        "hcp": HCP_VERSION,
        "msg_id": str(uuid.uuid4()),
        "type": message_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sender": sender.as_dict(),
        "receiver": receiver.as_dict(),
        "state": {"human": human_state.as_dict()},
        "payload": payload,
    }


def validate_envelope(envelope: Dict[str, Any]) -> None:
    required = ["hcp", "msg_id", "type", "timestamp", "sender", "receiver", "state", "payload"]
    missing = [key for key in required if key not in envelope]
    if missing:
        raise ValueError(f"Missing envelope fields: {', '.join(missing)}")
    if envelope["hcp"] != HCP_VERSION:
        raise ValueError("Unsupported HCP version")
    if not isinstance(envelope["payload"], dict):
        raise ValueError("Payload must be an object")
    state = envelope.get("state", {})
    if not isinstance(state, dict) or "human" not in state:
        raise ValueError("Missing human state")
    for section in ("sender", "receiver"):
        identity = envelope.get(section)
        if not isinstance(identity, dict) or "agent_id" not in identity or "fingerprint" not in identity:
            raise ValueError("Sender/receiver missing identity fields")


def signable_payload(envelope: Dict[str, Any]) -> str:
    data = dict(envelope)
    data.pop("sign", None)
    return canonical_json(data)
