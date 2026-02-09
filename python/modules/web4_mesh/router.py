from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .mesh_envelope import MeshEnvelope
from .peers import PeerRegistry
from .trust_mesh import DistributedTrustFSM, TrustLevel


@dataclass(frozen=True)
class MeshForwardingPolicy:
    max_hops: int = 3


@dataclass
class MeshRouter:
    registry: PeerRegistry
    trust: DistributedTrustFSM
    policy: MeshForwardingPolicy = MeshForwardingPolicy()

    def route(self, envelope: MeshEnvelope) -> Optional[MeshEnvelope]:
        if envelope.destination == envelope.origin:
            return envelope
        if envelope.destination in envelope.hops:
            return None
        if len(envelope.hops) >= self.policy.max_hops:
            return None
        if self.trust.get(envelope.destination) == TrustLevel.BLOCKED:
            return None
        if not self.registry.has(envelope.destination):
            return None
        return envelope.with_hop(envelope.destination)

    def broadcast(self, envelope: MeshEnvelope) -> List[MeshEnvelope]:
        routed: List[MeshEnvelope] = []
        for peer in self.registry.all_peers():
            if peer.peer_id == envelope.origin:
                continue
            if self.trust.get(peer.peer_id) == TrustLevel.BLOCKED:
                continue
            routed.append(envelope.with_hop(peer.peer_id))
        return routed
