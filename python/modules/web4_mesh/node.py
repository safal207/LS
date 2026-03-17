from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .mesh_envelope import MeshEnvelope
from .peers import Peer, PeerRegistry
from .router import MeshForwardingPolicy, MeshRouter
from .trust_mesh import DistributedTrustFSM

ANNOUNCE = "ANNOUNCE"
SYNC_GRAPH_CHUNK = "SYNC_GRAPH_CHUNK"
SYNC_GRAPH_REQUEST = "SYNC_GRAPH_REQUEST"
PUSH_REFLECTION = "PUSH_REFLECTION"


@dataclass
class Web4MeshNode:
    """Minimal in-memory Web4 Mesh node for local multi-node simulation."""

    peer_id: str
    address: str
    registry: PeerRegistry = field(default_factory=PeerRegistry)
    trust: DistributedTrustFSM = field(default_factory=DistributedTrustFSM)
    forwarding: MeshForwardingPolicy = field(default_factory=MeshForwardingPolicy)

    def __post_init__(self) -> None:
        self.router = MeshRouter(registry=self.registry, trust=self.trust, policy=self.forwarding)
        self.memory_graph: Dict[str, Dict[str, object]] = {}
        self.reflections: List[Dict[str, object]] = []
        self.registry.add(Peer(self.peer_id, self.address))
        self.trust.on_verified(self.peer_id)

    def add_peer(self, peer_id: str, address: str) -> None:
        self.registry.add(Peer(peer_id, address))
        self.trust.on_verified(peer_id)

    def announce(self) -> List[MeshEnvelope]:
        envelope = MeshEnvelope(
            message_type=ANNOUNCE,
            origin=self.peer_id,
            destination="*",
            payload={"peer_id": self.peer_id, "address": self.address},
        )
        return self.router.broadcast(envelope)

    def request_graph_chunk(self, destination: str, since: Optional[str] = None) -> Optional[MeshEnvelope]:
        envelope = MeshEnvelope(
            message_type=SYNC_GRAPH_REQUEST,
            origin=self.peer_id,
            destination=destination,
            payload={"since": since},
        )
        return self.router.route(envelope)

    def push_reflection(self, text: str, reflection_id: str) -> List[MeshEnvelope]:
        reflection = {"id": reflection_id, "text": text, "author": self.peer_id}
        self.reflections.append(reflection)
        self.memory_graph[reflection_id] = reflection
        envelope = MeshEnvelope(
            message_type=PUSH_REFLECTION,
            origin=self.peer_id,
            destination="*",
            payload=reflection,
        )
        return self.router.broadcast(envelope)

    def receive(self, envelope: MeshEnvelope) -> List[MeshEnvelope]:
        if envelope.message_type == ANNOUNCE:
            peer_id = str(envelope.payload.get("peer_id", envelope.origin))
            address = str(envelope.payload.get("address", f"mesh://{peer_id}"))
            self.add_peer(peer_id, address)
            return []

        if envelope.message_type == PUSH_REFLECTION:
            reflection_id = str(envelope.payload["id"])
            self.memory_graph[reflection_id] = dict(envelope.payload)
            self.reflections.append(dict(envelope.payload))
            return []

        if envelope.message_type == SYNC_GRAPH_REQUEST:
            if envelope.destination != self.peer_id:
                return []
            chunk = list(self.memory_graph.values())
            response = MeshEnvelope(
                message_type=SYNC_GRAPH_CHUNK,
                origin=self.peer_id,
                destination=envelope.origin,
                payload={"chunk": chunk},
            )
            routed = self.router.route(response)
            return [routed] if routed is not None else []

        if envelope.message_type == SYNC_GRAPH_CHUNK:
            chunk = envelope.payload.get("chunk", [])
            for node in chunk:
                if "id" in node:
                    self.memory_graph[str(node["id"])] = dict(node)
            return []

        return []
