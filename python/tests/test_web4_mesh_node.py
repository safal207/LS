from dataclasses import dataclass
from typing import Mapping

from modules.web4_mesh.mesh_envelope import MeshEnvelope
from modules.web4_mesh.node import (
    ANNOUNCE,
    PUSH_REFLECTION,
    SYNC_GRAPH_CHUNK,
    SYNC_GRAPH_REQUEST,
    RotatingMeshSigner,
    RotatingMeshVerifier,
    Web4MeshNode,
    Web4MeshNodeConfig,
)


@dataclass
class DummySigner:
    def sign(self, payload: Mapping[str, object]) -> str:
        return f"sig:{payload.get('id', 'na')}"

    def rotate_keys(self) -> str:
        return "k2"


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


def test_signed_envelope_without_verifier_is_rejected_when_signature_present() -> None:
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


def test_unsigned_envelope_without_verifier_is_accepted() -> None:
    node_b = Web4MeshNode("node-b", "mesh://b")

    envelope = MeshEnvelope(
        message_type=PUSH_REFLECTION,
        origin="node-a",
        destination="node-b",
        payload={"id": "r-plain", "text": "plain", "author": "node-a"},
        envelope_id="plain-1",
    )
    node_b.receive(envelope)
    assert "r-plain" in node_b.memory_graph


def test_empty_signature_without_verifier_is_treated_as_unsigned() -> None:
    node_b = Web4MeshNode("node-b", "mesh://b")
    envelope = MeshEnvelope(
        message_type=PUSH_REFLECTION,
        origin="node-a",
        destination="node-b",
        payload={"id": "r-empty-sig", "text": "ok", "author": "node-a", "signature": ""},
        envelope_id="empty-sig-1",
    )
    node_b.receive(envelope)
    assert "r-empty-sig" in node_b.memory_graph


def test_rotating_signer_with_key_history_verifier() -> None:
    signer = RotatingMeshSigner(signer_id="node-a")
    verifier = RotatingMeshVerifier(keyring={"node-a": dict(signer.key_history)})

    node_a = Web4MeshNode("node-a", "mesh://a", signer=signer)
    node_b = Web4MeshNode("node-b", "mesh://b", verifier=verifier)
    node_a.add_peer("node-b", "mesh://b")

    first = node_a.push_reflection("one", "r1")[0]
    node_b.receive(MeshEnvelope(message_type=PUSH_REFLECTION, origin="node-a", destination="node-b", payload=first.payload, envelope_id="first"))
    assert "r1" in node_b.memory_graph

    signer.rotate_keys()
    # old verifier keyring intentionally stale => reject new signatures
    second = node_a.push_reflection("two", "r2")[0]
    node_b.receive(MeshEnvelope(message_type=PUSH_REFLECTION, origin="node-a", destination="node-b", payload=second.payload, envelope_id="second"))
    assert "r2" not in node_b.memory_graph

    # update keyring with history/current and retry with fresh envelope
    verifier.keyring["node-a"] = dict(signer.key_history)
    node_b.trust.on_verified("node-a")
    third = node_a.push_reflection("three", "r3")[0]
    node_b.receive(MeshEnvelope(message_type=PUSH_REFLECTION, origin="node-a", destination="node-b", payload=third.payload, envelope_id="third"))
    assert "r3" in node_b.memory_graph


def test_ttl_gc_expired_removes_entries() -> None:
    node = Web4MeshNode("node-a", "mesh://a", config=Web4MeshNodeConfig(entry_ttl_seconds=1))
    node.push_reflection("ttl", "r-ttl")
    assert "r-ttl" in node.memory_graph
    removed = node.gc_expired(now=node._graph_inserted_at["r-ttl"] + 2)
    assert removed == 1
    assert "r-ttl" not in node.memory_graph
