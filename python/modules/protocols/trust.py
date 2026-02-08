from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TrustState(str, Enum):
    UNTRUSTED = "untrusted"
    PROBING = "probing"
    TRUSTED = "trusted"
    BLACKLISTED = "blacklisted"


@dataclass
class TrustTransition:
    state: TrustState
    reason: str


class TrustFSM:
    def __init__(self, initial: TrustState = TrustState.UNTRUSTED) -> None:
        self.state = initial

    def on_valid_handshake(self) -> TrustTransition:
        if self.state == TrustState.UNTRUSTED:
            self.state = TrustState.PROBING
            return TrustTransition(self.state, "valid_handshake")
        return TrustTransition(self.state, "ignored")

    def on_verified_knowledge(self) -> TrustTransition:
        if self.state in (TrustState.PROBING, TrustState.TRUSTED):
            self.state = TrustState.TRUSTED
            return TrustTransition(self.state, "verified_knowledge")
        return TrustTransition(self.state, "ignored")

    def on_conflict(self) -> TrustTransition:
        if self.state == TrustState.PROBING:
            self.state = TrustState.UNTRUSTED
            return TrustTransition(self.state, "conflict")
        if self.state == TrustState.TRUSTED:
            self.state = TrustState.PROBING
            return TrustTransition(self.state, "conflict")
        return TrustTransition(self.state, "ignored")

    def on_malicious(self) -> TrustTransition:
        self.state = TrustState.BLACKLISTED
        return TrustTransition(self.state, "malicious")

    def on_manual_override(self) -> TrustTransition:
        if self.state == TrustState.BLACKLISTED:
            self.state = TrustState.PROBING
            return TrustTransition(self.state, "manual_override")
        return TrustTransition(self.state, "ignored")
