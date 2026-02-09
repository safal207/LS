from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..protocols.cip import CipIdentity, CipState, build_envelope, validate_envelope
from ..protocols.trust import TrustFSM, TrustTransition


@dataclass
class CipRuntime:
    identity: CipIdentity
    trust_fsm: TrustFSM

    def build_hello(self, receiver: CipIdentity, state: Optional[CipState] = None) -> Dict[str, Any]:
        payload = {"handshake": "hello"}
        return build_envelope("HELLO", self.identity, receiver, payload, state=state)

    def build_ack(self, receiver: CipIdentity, state: Optional[CipState] = None) -> Dict[str, Any]:
        payload = {"handshake": "ack"}
        return build_envelope("HELLO_ACK", self.identity, receiver, payload, state=state)

    def handle_envelope(self, envelope: Dict[str, Any]) -> TrustTransition | None:
        validate_envelope(envelope)
        message_type = envelope.get("type")
        if message_type == "HELLO":
            return self.trust_fsm.on_valid_handshake()
        if message_type == "FACT_CONFIRM":
            return self.trust_fsm.on_verified_knowledge()
        if message_type == "FACT_CHALLENGE":
            return self.trust_fsm.on_conflict()
        return None
