from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any, Dict

from .cognitive_transaction import CognitiveTransaction


@dataclass(frozen=True)
class LTPEnvelope:
    """L-Thread protocol style envelope for cognitive event transport."""

    sender: str
    receiver: str
    event: str
    payload: Dict[str, Any]
    signature: str

    @staticmethod
    def from_transaction(tx: CognitiveTransaction, sender: str, receiver: str, signing_key: str) -> "LTPEnvelope":
        body = {
            "tx_id": tx.tx_id,
            "timestamp": tx.timestamp,
            "actor": tx.actor,
            "action": tx.action,
            "payload": tx.payload,
        }
        signature = sha256(f"{sender}:{receiver}:{tx.tx_id}:{signing_key}".encode("utf-8")).hexdigest()
        return LTPEnvelope(sender=sender, receiver=receiver, event=tx.action, payload=body, signature=signature)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
