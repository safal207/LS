from __future__ import annotations

import asyncio
import logging

from modules.web4_mesh import Web4MeshNode, WebSocketTransport

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("run_mesh_ws")


async def start_node(peer_id: str, host: str, port: int) -> tuple[Web4MeshNode, WebSocketTransport]:
    node = Web4MeshNode(peer_id=peer_id, address=f"ws://{host}:{port}")
    transport = WebSocketTransport(node=node, host=host, port=port)
    await transport.start()
    return node, transport


async def demo() -> None:
    host = "127.0.0.1"

    node_a, t_a = await start_node("node-a", host, 9001)
    node_b, t_b = await start_node("node-b", host, 9002)
    node_c, t_c = await start_node("node-c", host, 9003)

    node_a.add_peer("node-b", t_b.listen_uri)
    node_a.add_peer("node-c", t_c.listen_uri)
    node_b.add_peer("node-a", t_a.listen_uri)
    node_b.add_peer("node-c", t_c.listen_uri)
    node_c.add_peer("node-a", t_a.listen_uri)
    node_c.add_peer("node-b", t_b.listen_uri)

    await t_a.connect_to_peer(t_b.listen_uri)
    await t_a.connect_to_peer(t_c.listen_uri)
    await t_b.connect_to_peer(t_a.listen_uri)
    await t_c.connect_to_peer(t_a.listen_uri)

    announce_envelopes = node_a.announce()
    await t_a.send_many_routed(announce_envelopes)

    reflection_envelopes = node_a.push_reflection("hello mesh", "r1")
    await t_a.send_many_routed(reflection_envelopes)
    await asyncio.sleep(0.3)

    logger.info("node-b graph: %s", list(node_b.memory_graph.keys()))
    logger.info("node-c graph: %s", list(node_c.memory_graph.keys()))

    node_d, t_d = await start_node("node-d", host, 9004)
    node_d.add_peer("node-a", t_a.listen_uri)
    node_a.add_peer("node-d", t_d.listen_uri)
    await t_d.connect_to_peer(t_a.listen_uri)

    request = node_d.request_graph_chunk("node-a")
    if request is not None:
        await t_d.send(request, t_a.listen_uri)

    await asyncio.sleep(0.5)
    logger.info("node-d graph after sync: %s", list(node_d.memory_graph.keys()))

    await asyncio.gather(t_a.stop(), t_b.stop(), t_c.stop(), t_d.stop())


if __name__ == "__main__":
    asyncio.run(demo())
