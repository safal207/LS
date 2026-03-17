from modules.web4_mesh.mesh_envelope import MeshEnvelope
from modules.web4_mesh.node import (
    ANNOUNCE,
    PUSH_REFLECTION,
    SYNC_GRAPH_CHUNK,
    SYNC_GRAPH_REQUEST,
    Web4MeshNode,
)


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
