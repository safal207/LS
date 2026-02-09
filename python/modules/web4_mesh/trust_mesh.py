from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict


class TrustLevel(str, Enum):
    UNKNOWN = "unknown"
    PROBING = "probing"
    TRUSTED = "trusted"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class TrustLink:
    peer_id: str
    level: TrustLevel
    reason: str


class DistributedTrustFSM:
    def __init__(self) -> None:
        self._levels: Dict[str, TrustLevel] = {}

    def get(self, peer_id: str) -> TrustLevel:
        return self._levels.get(peer_id, TrustLevel.UNKNOWN)

    def on_handshake(self, peer_id: str) -> TrustLink:
        level = TrustLevel.PROBING if self.get(peer_id) == TrustLevel.UNKNOWN else self.get(peer_id)
        self._levels[peer_id] = level
        return TrustLink(peer_id, level, "handshake")

    def on_verified(self, peer_id: str) -> TrustLink:
        self._levels[peer_id] = TrustLevel.TRUSTED
        return TrustLink(peer_id, TrustLevel.TRUSTED, "verified")

    def on_conflict(self, peer_id: str) -> TrustLink:
        current = self.get(peer_id)
        if current == TrustLevel.TRUSTED:
            self._levels[peer_id] = TrustLevel.PROBING
            return TrustLink(peer_id, TrustLevel.PROBING, "conflict")
        self._levels[peer_id] = TrustLevel.BLOCKED
        return TrustLink(peer_id, TrustLevel.BLOCKED, "conflict")

    def propagate(self, source_peer: str, target_peer: str) -> TrustLink:
        source_level = self.get(source_peer)
        if source_level == TrustLevel.TRUSTED:
            return self.on_handshake(target_peer)
        return TrustLink(target_peer, self.get(target_peer), "no_propagation")
