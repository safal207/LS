from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, MutableMapping, Optional, Protocol, Sequence, Set

from .mesh_envelope import MeshEnvelope
from .observability_mesh import MeshObservabilityHub
from .peers import Peer, PeerRegistry
from .router import MeshForwardingPolicy, MeshRouter
from .trust_mesh import DistributedTrustFSM, TrustLevel

ANNOUNCE = "ANNOUNCE"
SYNC_GRAPH_CHUNK = "SYNC_GRAPH_CHUNK"
SYNC_GRAPH_REQUEST = "SYNC_GRAPH_REQUEST"
PUSH_REFLECTION = "PUSH_REFLECTION"


class MeshEnvelopeSigner(Protocol):
    """Optional signature adapter for envelope payloads."""

    def sign(self, payload: Mapping[str, object]) -> str: ...


class MeshEnvelopeVerifier(Protocol):
    """Optional signature verifier for envelope payloads."""

    def verify(self, payload: Mapping[str, object], signature: str, signer_id: str) -> bool: ...


@dataclass(frozen=True)
class Web4MeshNodeConfig:
    max_graph_chunk_size: int = 256
    allow_self_reflection_duplicates: bool = False


@dataclass
class Web4MeshNode:
    """Envelope-first in-memory mesh node aligned with LS trust + observability flow."""

    peer_id: str
    address: str
    registry: PeerRegistry = field(default_factory=PeerRegistry)
    trust: DistributedTrustFSM = field(default_factory=DistributedTrustFSM)
    forwarding: MeshForwardingPolicy = field(default_factory=MeshForwardingPolicy)
    observability: MeshObservabilityHub = field(default_factory=MeshObservabilityHub)
    config: Web4MeshNodeConfig = field(default_factory=Web4MeshNodeConfig)
    signer: MeshEnvelopeSigner | None = None
    verifier: MeshEnvelopeVerifier | None = None

    def __post_init__(self) -> None:
        self.router = MeshRouter(registry=self.registry, trust=self.trust, policy=self.forwarding)
        self.memory_graph: MutableMapping[str, Dict[str, object]] = {}
        self.reflections: List[Dict[str, object]] = []
        self._seen_envelope_ids: Set[str] = set()
        self._seen_reflection_ids: Set[str] = set()

        self.registry.add(Peer(self.peer_id, self.address))
        self.trust.on_verified(self.peer_id)
        self.observability.record("mesh_node_started", {"peer_id": self.peer_id, "address": self.address})

    def add_peer(self, peer_id: str, address: str) -> None:
        self.registry.add(Peer(peer_id, address))
        self.trust.on_handshake(peer_id)
        self.observability.record("mesh_peer_added", {"peer_id": peer_id, "address": address})

    def announce(self) -> List[MeshEnvelope]:
        payload: Dict[str, object] = {
            "peer_id": self.peer_id,
            "address": self.address,
            "capabilities": [
                ANNOUNCE,
                PUSH_REFLECTION,
                SYNC_GRAPH_REQUEST,
                SYNC_GRAPH_CHUNK,
            ],
        }
        payload = self._apply_signature(payload)

        envelope = MeshEnvelope(
            message_type=ANNOUNCE,
            origin=self.peer_id,
            destination="*",
            payload=payload,
        )
        routed = self.router.broadcast(envelope)
        self.observability.record("mesh_announce_broadcast", {"peer_count": len(routed)})
        return routed

    def request_graph_chunk(self, destination: str, since: Optional[str] = None) -> Optional[MeshEnvelope]:
        payload: Dict[str, object] = {
            "since": since,
            "limit": self.config.max_graph_chunk_size,
        }
        payload = self._apply_signature(payload)

        envelope = MeshEnvelope(
            message_type=SYNC_GRAPH_REQUEST,
            origin=self.peer_id,
            destination=destination,
            payload=payload,
        )
        routed = self.router.route(envelope)
        self.observability.record(
            "mesh_graph_sync_requested",
            {"destination": destination, "routed": routed is not None},
        )
        return routed

    def push_reflection(self, text: str, reflection_id: str) -> List[MeshEnvelope]:
        reflection = {
            "id": reflection_id,
            "text": text,
            "author": self.peer_id,
        }
        if reflection_id in self._seen_reflection_ids and not self.config.allow_self_reflection_duplicates:
            self.observability.record("mesh_reflection_duplicate_skipped", {"reflection_id": reflection_id})
            return []

        self._seen_reflection_ids.add(reflection_id)
        self.reflections.append(reflection)
        self.memory_graph[reflection_id] = reflection

        payload = self._apply_signature(reflection)
        envelope = MeshEnvelope(
            message_type=PUSH_REFLECTION,
            origin=self.peer_id,
            destination="*",
            payload=payload,
        )
        routed = self.router.broadcast(envelope)
        self.observability.record("mesh_reflection_broadcast", {"reflection_id": reflection_id, "peer_count": len(routed)})
        return routed

    def receive(self, envelope: MeshEnvelope) -> List[MeshEnvelope]:
        if envelope.envelope_id in self._seen_envelope_ids:
            self.observability.record("mesh_envelope_deduplicated", {"envelope_id": envelope.envelope_id})
            return []
        self._seen_envelope_ids.add(envelope.envelope_id)

        if self.trust.get(envelope.origin) == TrustLevel.BLOCKED:
            self.observability.record("mesh_blocked_message", {"origin": envelope.origin, "message_type": envelope.message_type})
            return []

        if not self._verify_signature_if_present(envelope):
            self.trust.on_conflict(envelope.origin)
            self.observability.record(
                "mesh_signature_verification_failed",
                {"origin": envelope.origin, "message_type": envelope.message_type},
            )
            return []

        if envelope.message_type == ANNOUNCE:
            return self._on_announce(envelope)
        if envelope.message_type == PUSH_REFLECTION:
            return self._on_reflection(envelope)
        if envelope.message_type == SYNC_GRAPH_REQUEST:
            return self._on_sync_request(envelope)
        if envelope.message_type == SYNC_GRAPH_CHUNK:
            return self._on_sync_chunk(envelope)

        self.observability.record("mesh_unknown_message", {"message_type": envelope.message_type})
        return []

    def _on_announce(self, envelope: MeshEnvelope) -> List[MeshEnvelope]:
        peer_id = str(envelope.payload.get("peer_id", envelope.origin))
        address = str(envelope.payload.get("address", f"mesh://{peer_id}"))
        self.add_peer(peer_id, address)
        self.trust.on_verified(peer_id)
        self.observability.record("mesh_announce_received", {"peer_id": peer_id})
        return []

    def _on_reflection(self, envelope: MeshEnvelope) -> List[MeshEnvelope]:
        reflection_id = str(envelope.payload.get("id", ""))
        if not reflection_id:
            self.observability.record("mesh_reflection_invalid", {"origin": envelope.origin})
            return []
        if reflection_id in self._seen_reflection_ids:
            self.observability.record("mesh_reflection_deduplicated", {"reflection_id": reflection_id})
            return []

        sanitized_reflection = {
            "id": reflection_id,
            "text": str(envelope.payload.get("text", "")),
            "author": str(envelope.payload.get("author", envelope.origin)),
        }
        self._seen_reflection_ids.add(reflection_id)
        self.memory_graph[reflection_id] = sanitized_reflection
        self.reflections.append(sanitized_reflection)
        self.trust.on_handshake(envelope.origin)
        self.observability.record("mesh_reflection_received", {"reflection_id": reflection_id, "origin": envelope.origin})
        return []

    def _on_sync_request(self, envelope: MeshEnvelope) -> List[MeshEnvelope]:
        if envelope.destination != self.peer_id:
            return []

        requested_limit = envelope.payload.get("limit", self.config.max_graph_chunk_size)
        if not isinstance(requested_limit, int) or requested_limit <= 0:
            requested_limit = self.config.max_graph_chunk_size
        effective_limit = min(requested_limit, self.config.max_graph_chunk_size)

        chunk = list(self.memory_graph.values())[:effective_limit]
        payload: Dict[str, object] = {
            "chunk": chunk,
            "chunk_size": len(chunk),
        }
        payload = self._apply_signature(payload)

        response = MeshEnvelope(
            message_type=SYNC_GRAPH_CHUNK,
            origin=self.peer_id,
            destination=envelope.origin,
            payload=payload,
        )
        routed = self.router.route(response)
        self.observability.record(
            "mesh_graph_sync_chunk_created",
            {"destination": envelope.origin, "chunk_size": len(chunk), "routed": routed is not None},
        )
        return [routed] if routed is not None else []

    def _on_sync_chunk(self, envelope: MeshEnvelope) -> List[MeshEnvelope]:
        chunk = envelope.payload.get("chunk", [])
        if not isinstance(chunk, Sequence):
            self.observability.record("mesh_graph_sync_invalid_chunk", {"origin": envelope.origin})
            return []

        inserted = 0
        for node in chunk:
            if not isinstance(node, Mapping):
                continue
            node_id = node.get("id")
            if not isinstance(node_id, str) or not node_id:
                continue
            normalized = {
                "id": node_id,
                "text": str(node.get("text", "")),
                "author": str(node.get("author", envelope.origin)),
            }
            if node_id not in self.memory_graph:
                inserted += 1
            self.memory_graph[node_id] = normalized
            self._seen_reflection_ids.add(node_id)

        self.trust.on_handshake(envelope.origin)
        self.observability.record("mesh_graph_sync_applied", {"origin": envelope.origin, "inserted": inserted})
        return []

    def _apply_signature(self, payload: Dict[str, object]) -> Dict[str, object]:
        if self.signer is None:
            return payload
        signed_payload = dict(payload)
        signed_payload["signature"] = self.signer.sign(payload)
        signed_payload["signer_id"] = self.peer_id
        return signed_payload

    def _verify_signature_if_present(self, envelope: MeshEnvelope) -> bool:
        signature = envelope.payload.get("signature")
        signer_id = envelope.payload.get("signer_id", envelope.origin)
        if not isinstance(signature, str):
            return True
        if self.verifier is None:
            return False
        payload = dict(envelope.payload)
        payload.pop("signature", None)
        payload.pop("signer_id", None)
        return self.verifier.verify(payload, signature, str(signer_id))
