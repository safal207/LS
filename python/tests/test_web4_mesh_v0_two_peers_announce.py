"""Web4 Mesh v0 (plan W3): two peer processes exchange at least one ANNOUNCE envelope over WebSocket transport."""

from __future__ import annotations

import asyncio

from modules.web4_mesh import Web4MeshNode, WebSocketTransport
from modules.web4_mesh.node import ANNOUNCE


def test_v0_two_peers_swap_announce() -> None:
    """Peer A broadcasts ANNOUNCE; peer B's registry ends up knowing peer A."""

    async def _run() -> None:
        node_a = Web4MeshNode("node-a", "ws://127.0.0.1:9131")
        node_b = Web4MeshNode("node-b", "ws://127.0.0.1:9132")
        t_a = WebSocketTransport(node=node_a, host="127.0.0.1", port=9131, run_id="v0-announce")
        t_b = WebSocketTransport(node=node_b, host="127.0.0.1", port=9132, run_id="v0-announce")
        await t_a.start()
        await t_b.start()
        try:
            node_a.add_peer("node-b", t_b.listen_uri)
            node_b.add_peer("node-a", t_a.listen_uri)
            await t_a.connect_to_peer(t_b.listen_uri)
            await t_b.connect_to_peer(t_a.listen_uri)

            envs = node_a.announce()
            assert envs, "announce should produce at least one envelope"
            assert all(e.message_type == ANNOUNCE for e in envs)
            await t_a.send_many_routed(envs)
            await asyncio.sleep(0.35)

            assert node_b.registry.has("node-a"), "B should learn A from ANNOUNCE"
            peer = node_b.registry.get("node-a")
            assert peer is not None
            assert peer.peer_id == "node-a"
        finally:
            await asyncio.gather(t_a.stop(), t_b.stop())

    asyncio.run(_run())
