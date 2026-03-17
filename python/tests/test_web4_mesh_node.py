from dataclasses import dataclass
from typing import Mapping

from modules.web4_mesh.mesh_envelope import MeshEnvelope
from modules.web4_mesh.node import (
    ANNOUNCE,
    PUSH_REFLECTION,
    SYNC_GRAPH_CHUNK,
    SYNC_GRAPH_REQUEST,
    Web4MeshNode,
    Web4MeshNodeConfig,
)


@dataclass
class DummySigner:
    def sign(self, payload: Mapping[str, object]) -> str:
        return f"sig:{payload.get('id', 'na')}"


@dataclass
class DummyVerifier:
    valid_signers: set[str]

    def verify(self, payload: Mapping[str, object], signature: str, signer_id: str) -> bool:
        return signer_id in self.valid_signers and signature.startswith("sig:")


def test_node_announce_and_peer_discovery() -> None:
    node_a = Web4MeshNode("node-a", "mesh://a")
    node_b = Web4MeshNode("node-b", "mesh://b")
    node_a.add_peer("node-b", "mesh://b")

    announces = node_a.announce()
    assert announces
    node_b.receive(announces[0])
    assert node_b.registry.has("node-a")


def test_node_reflection_broadcast_and_sync() -> None:
    node_a = Web4MeshNode("node-a", "mesh://a")
    node_b = Web4MeshNode("node-b", "mesh://b")

    node_a.add_peer("node-b", "mesh://b")
    node_b.add_peer("node-a", "mesh://a")

    broadcasts = node_a.push_reflection("hello mesh", "r1")
    assert broadcasts
    reflected = MeshEnvelope(
        message_type=PUSH_REFLECTION,
        origin="node-a",
        destination="node-b",
        payload=broadcasts[0].payload,
    )
    node_b.receive(reflected)
    assert "r1" in node_b.memory_graph

    request = node_b.request_graph_chunk("node-a")
    assert request is not None
    assert request.message_type == SYNC_GRAPH_REQUEST

    chunk_envelopes = node_a.receive(request)
    assert chunk_envelopes
    assert chunk_envelopes[0].message_type == SYNC_GRAPH_CHUNK

    node_b.receive(chunk_envelopes[0])
    assert "r1" in node_b.memory_graph


def test_node_receives_announce_message() -> None:
    node = Web4MeshNode("node-a", "mesh://a")
    envelope = MeshEnvelope(
        message_type=ANNOUNCE,
        origin="node-b",
        destination="*",
        payload={"peer_id": "node-b", "address": "mesh://b"},
    )
    node.receive(envelope)
    assert node.registry.has("node-b")


def test_node_deduplicates_reflection_by_id() -> None:
    node = Web4MeshNode("node-a", "mesh://a")
    node.push_reflection("hello", "r1")
    second = node.push_reflection("hello again", "r1")
    assert second == []


def test_node_sync_chunk_respects_limit() -> None:
    node_a = Web4MeshNode("node-a", "mesh://a", config=Web4MeshNodeConfig(max_graph_chunk_size=1))
    node_b = Web4MeshNode("node-b", "mesh://b")
    node_a.add_peer("node-b", "mesh://b")

    node_a.push_reflection("a", "r1")
    node_a.push_reflection("b", "r2")

    request = MeshEnvelope(
        message_type=SYNC_GRAPH_REQUEST,
        origin="node-b",
        destination="node-a",
        payload={"limit": 100},
    )
    response = node_a.receive(request)
    assert response
    chunk = response[0].payload["chunk"]
    assert len(chunk) == 1


def test_signed_envelope_is_verified() -> None:
    signer = DummySigner()
    verifier = DummyVerifier(valid_signers={"node-a"})

    node_a = Web4MeshNode("node-a", "mesh://a", signer=signer)
    node_b = Web4MeshNode("node-b", "mesh://b", verifier=verifier)
    node_a.add_peer("node-b", "mesh://b")

    envelopes = node_a.push_reflection("secured", "r-sec")
    assert envelopes
    secured = MeshEnvelope(
        message_type=PUSH_REFLECTION,
        origin="node-a",
        destination="node-b",
        payload=envelopes[0].payload,
        envelope_id="e-1",
    )

    node_b.receive(secured)
    assert "r-sec" in node_b.memory_graph


def test_signed_envelope_without_verifier_is_rejected() -> None:
    signer = DummySigner()
    node_a = Web4MeshNode("node-a", "mesh://a", signer=signer)
    node_b = Web4MeshNode("node-b", "mesh://b")
    node_a.add_peer("node-b", "mesh://b")

    envelopes = node_a.push_reflection("secured", "r-sec")
    rejected = MeshEnvelope(
        message_type=PUSH_REFLECTION,
        origin="node-a",
        destination="node-b",
        payload=envelopes[0].payload,
        envelope_id="e-2",
    )
    node_b.receive(rejected)
    assert "r-sec" not in node_b.memory_graph
