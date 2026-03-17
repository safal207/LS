import asyncio

from modules.web4_mesh import Web4MeshNode
from modules.web4_mesh.mesh_envelope import MeshEnvelope
from modules.web4_mesh.node import PUSH_REFLECTION
from modules.web4_mesh.transport_ws import WebSocketTransport


def test_ws_transport_serialization_roundtrip() -> None:
    node = Web4MeshNode("node-a", "ws://127.0.0.1:9101")
    transport = WebSocketTransport(node=node, host="127.0.0.1", port=9101)
    envelope = MeshEnvelope(
        message_type=PUSH_REFLECTION,
        origin="node-a",
        destination="node-b",
        payload={"id": "r1", "text": "hello", "author": "node-a"},
    )

    raw = transport._serialize_envelope(envelope)
    decoded = transport._deserialize_envelope(raw)
    assert decoded is not None
    assert decoded.message_type == PUSH_REFLECTION
    assert decoded.payload["id"] == "r1"
    assert decoded.payload["origin_address"] == "ws://127.0.0.1:9101"


def test_ws_transport_reflection_and_sync_late_join() -> None:
    async def _run() -> None:
        node_a = Web4MeshNode("node-a", "ws://127.0.0.1:9111")
        node_b = Web4MeshNode("node-b", "ws://127.0.0.1:9112")
        t_a = WebSocketTransport(node=node_a, port=9111)
        t_b = WebSocketTransport(node=node_b, port=9112)
        await t_a.start()
        await t_b.start()

        node_a.add_peer("node-b", t_b.listen_uri)
        node_b.add_peer("node-a", t_a.listen_uri)

        await t_a.connect_to_peer(t_b.listen_uri)
        await t_b.connect_to_peer(t_a.listen_uri)

        envs = node_a.push_reflection("hello", "r1")
        await t_a.send_many_routed(envs)
        await asyncio.sleep(0.3)
        assert "r1" in node_b.memory_graph

        node_d = Web4MeshNode("node-d", "ws://127.0.0.1:9114")
        t_d = WebSocketTransport(node=node_d, port=9114)
        await t_d.start()

        node_d.add_peer("node-a", t_a.listen_uri)
        node_a.add_peer("node-d", t_d.listen_uri)
        await t_d.connect_to_peer(t_a.listen_uri)

        req = node_d.request_graph_chunk("node-a")
        assert req is not None
        await t_d.send(req, t_a.listen_uri)
        await asyncio.sleep(0.4)
        assert "r1" in node_d.memory_graph

        await asyncio.gather(t_a.stop(), t_b.stop(), t_d.stop())

    asyncio.run(_run())
