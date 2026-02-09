from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class Peer:
    peer_id: str
    address: str
    capabilities: Iterable[str] = field(default_factory=tuple)


class PeerRegistry:
    def __init__(self) -> None:
        self._peers: Dict[str, Peer] = {}

    def add(self, peer: Peer) -> None:
        self._peers[peer.peer_id] = peer

    def remove(self, peer_id: str) -> None:
        self._peers.pop(peer_id, None)

    def get(self, peer_id: str) -> Optional[Peer]:
        return self._peers.get(peer_id)

    def all_peers(self) -> List[Peer]:
        return list(self._peers.values())

    def has(self, peer_id: str) -> bool:
        return peer_id in self._peers
