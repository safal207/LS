from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional

import websockets
from websockets.exceptions import ConnectionClosed

from .mesh_envelope import MeshEnvelope
from .node import Web4MeshNode

logger = logging.getLogger(__name__)


@dataclass
class WebSocketTransport:
    """Async WebSocket transport for cross-process Web4 mesh communication."""

    node: Web4MeshNode
    host: str = "127.0.0.1"
    port: int = 9001
    _server: websockets.asyncio.server.Server | None = field(default=None, init=False)
    _outgoing: Dict[str, websockets.ClientConnection] = field(default_factory=dict, init=False)
    _reader_tasks: list[asyncio.Task[None]] = field(default_factory=list, init=False)

    @property
    def listen_uri(self) -> str:
        return f"ws://{self.host}:{self.port}"

    async def start(self) -> None:
        async def handler(conn: websockets.ServerConnection) -> None:
            try:
                async for raw in conn:
                    envelope = self._deserialize_envelope(raw)
                    if envelope is None:
                        continue
                    await self._accept_and_dispatch(envelope)
            except ConnectionClosed:
                logger.debug("Inbound connection closed for %s", self.node.peer_id)

        self._server = await websockets.serve(handler, self.host, self.port)
        logger.info("WebSocket transport started for %s at %s", self.node.peer_id, self.listen_uri)

    async def stop(self) -> None:
        for task in self._reader_tasks:
            task.cancel()
        self._reader_tasks.clear()

        for conn in list(self._outgoing.values()):
            try:
                await conn.close()
            except Exception:
                logger.debug("Failed closing outgoing websocket", exc_info=True)
        self._outgoing.clear()

        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def connect_to_peer(self, uri: str) -> None:
        if uri in self._outgoing and not self._outgoing[uri].close_code:
            return
        conn = await websockets.connect(uri)
        self._outgoing[uri] = conn
        self._reader_tasks.append(asyncio.create_task(self._read_loop(conn, uri)))

    async def send(self, envelope: MeshEnvelope, peer_uri: str) -> None:
        await self.connect_to_peer(peer_uri)
        conn = self._outgoing[peer_uri]
        await conn.send(self._serialize_envelope(envelope))

    async def broadcast(self, envelope: MeshEnvelope) -> int:
        sent = 0
        for uri in list(self._outgoing.keys()):
            try:
                await self.send(envelope, uri)
                sent += 1
            except Exception:
                logger.warning("Broadcast failed from %s to %s", self.node.peer_id, uri, exc_info=True)
        return sent

    async def send_routed(self, envelope: MeshEnvelope) -> bool:
        peer = self.node.registry.get(envelope.destination)
        if peer is None:
            logger.debug("Unknown destination peer %s for %s", envelope.destination, self.node.peer_id)
            return False
        await self.send(envelope, peer.address)
        return True

    async def send_many_routed(self, envelopes: Iterable[MeshEnvelope]) -> int:
        delivered = 0
        for envelope in envelopes:
            if envelope.destination == "*":
                delivered += await self.broadcast(envelope)
                continue
            ok = await self.send_routed(envelope)
            delivered += int(ok)
        return delivered

    async def _read_loop(self, conn: websockets.ClientConnection, uri: str) -> None:
        try:
            async for raw in conn:
                envelope = self._deserialize_envelope(raw)
                if envelope is None:
                    continue
                await self._accept_and_dispatch(envelope)
        except ConnectionClosed:
            logger.debug("Peer connection closed %s -> %s", self.node.peer_id, uri)
        finally:
            self._outgoing.pop(uri, None)

    async def _accept_and_dispatch(self, envelope: MeshEnvelope) -> None:
        self._learn_origin_address(envelope)
        out = self.node.receive(envelope)
        if out:
            await self.send_many_routed(out)

    def _learn_origin_address(self, envelope: MeshEnvelope) -> None:
        origin_address = envelope.payload.get("origin_address")
        if not isinstance(origin_address, str):
            return
        if not origin_address.startswith("ws://"):
            return
        if not self.node.registry.has(envelope.origin):
            self.node.add_peer(envelope.origin, origin_address)

    def _serialize_envelope(self, env: MeshEnvelope) -> str:
        payload = dict(env.payload)
        payload.setdefault("origin_address", self.listen_uri)
        data = {
            "message_type": env.message_type,
            "origin": env.origin,
            "destination": env.destination,
            "payload": payload,
            "hops": list(env.hops),
            "envelope_id": env.envelope_id or str(uuid.uuid4()),
            "created_at": env.created_at,
        }
        return json.dumps(data, ensure_ascii=False)

    def _deserialize_envelope(self, raw: str) -> Optional[MeshEnvelope]:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Invalid envelope JSON for node %s", self.node.peer_id)
            return None
        try:
            return MeshEnvelope(
                message_type=str(data.get("message_type")),
                origin=str(data.get("origin")),
                destination=str(data.get("destination")),
                payload=data.get("payload", {}),
                hops=list(data.get("hops", [])),
                envelope_id=str(data.get("envelope_id") or uuid.uuid4()),
                created_at=str(data.get("created_at") or ""),
            )
        except Exception:
            logger.warning("Envelope decode failed for node %s", self.node.peer_id, exc_info=True)
            return None
