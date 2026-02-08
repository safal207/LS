from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict

from .cip import validate_envelope
from .trust import TrustFSM, TrustTransition


Handler = Callable[[Dict[str, Any]], None]


@dataclass
class RouterResult:
    transition: TrustTransition | None
    handled: bool


class ProtocolRouter:
    def __init__(self, trust: TrustFSM | None = None) -> None:
        self._trust = trust or TrustFSM()
        self._handlers: Dict[str, Handler] = {}

    @property
    def trust(self) -> TrustFSM:
        return self._trust

    def on(self, message_type: str, handler: Handler) -> None:
        self._handlers[message_type] = handler

    def dispatch(self, envelope: Dict[str, Any]) -> RouterResult:
        validate_envelope(envelope)
        message_type = envelope.get("type")
        handler = self._handlers.get(message_type)
        if handler:
            handler(envelope)
            return RouterResult(None, True)
        return RouterResult(None, False)

    def register_trust_signals(self) -> None:
        self.on("HELLO", lambda _env: self._trust.on_valid_handshake())
        self.on("FACT_CONFIRM", lambda _env: self._trust.on_verified_knowledge())
        self.on("FACT_CHALLENGE", lambda _env: self._trust.on_conflict())
