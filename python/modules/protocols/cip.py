from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable
import json
import uuid


CIP_VERSION = "1.0"


@dataclass(frozen=True)
class CipIdentity:
    agent_id: str
    fingerprint: str
    capabilities: Iterable[str] = field(default_factory=tuple)
    pubkey: str | None = None

    def as_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "agent_id": self.agent_id,
            "fingerprint": self.fingerprint,
        }
        if self.capabilities:
            data["capabilities"] = list(self.capabilities)
        if self.pubkey:
            data["pubkey"] = self.pubkey
        return data


@dataclass(frozen=True)
class CipState:
    presence: str
    lri: int
    kernel_signals: Iterable[str] = field(default_factory=tuple)
    intent: str | None = None

    def as_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "presence": self.presence,
            "lri": self.lri,
        }
        if self.kernel_signals:
            data["kernel_signals"] = list(self.kernel_signals)
        if self.intent is not None:
            data["intent"] = self.intent
        return data


def canonical_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_envelope(
    message_type: str,
    sender: CipIdentity,
    receiver: CipIdentity,
    payload: Dict[str, Any],
    state: CipState | None = None,
    trust: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    envelope: Dict[str, Any] = {
        "cip": CIP_VERSION,
        "msg_id": str(uuid.uuid4()),
        "type": message_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sender": sender.as_dict(),
        "receiver": receiver.as_dict(),
        "payload": payload,
    }
    if trust:
        envelope["trust"] = trust
    if state:
        envelope["state"] = state.as_dict()
    return envelope


def validate_envelope(envelope: Dict[str, Any]) -> None:
    required = ["cip", "msg_id", "type", "timestamp", "sender", "receiver", "payload"]
    missing = [key for key in required if key not in envelope]
    if missing:
        raise ValueError(f"Missing envelope fields: {', '.join(missing)}")
    if envelope["cip"] != CIP_VERSION:
        raise ValueError("Unsupported CIP version")
    if not isinstance(envelope["payload"], dict):
        raise ValueError("Payload must be an object")
    sender = envelope["sender"]
    receiver = envelope["receiver"]
    if not isinstance(sender, dict) or not isinstance(receiver, dict):
        raise ValueError("Sender/receiver must be objects")
    for required_key in ("agent_id", "fingerprint"):
        if required_key not in sender or required_key not in receiver:
            raise ValueError("Sender/receiver missing identity fields")


def signable_payload(envelope: Dict[str, Any]) -> str:
    data = dict(envelope)
    data.pop("sign", None)
    return canonical_json(data)
