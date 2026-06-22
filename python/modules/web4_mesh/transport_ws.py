from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, Optional

import websockets
from websockets.asyncio.client import ClientConnection
from websockets.asyncio.server import Server, ServerConnection
from websockets.exceptions import ConnectionClosed
from websockets.protocol import State

from .mesh_envelope import MeshEnvelope
from .node import Web4MeshNode

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeliveryEvent:
    run: str
    envelope_id: str
    origin: str
    destination: str
    latency_s: float
    delivered_bool: bool


@dataclass
class WebSocketTransport:
    """Async WebSocket transport for cross-process Web4 mesh communication."""

    node: Web4MeshNode
    host: str = "127.0.0.1"
    port: int = 9001
    on_delivery: Callable[[DeliveryEvent], None] | None = None
    run_id: str = "default"
    _server: Server | None = field(default=None, init=False)
    _outgoing: Dict[str, ClientConnection] = field(default_factory=dict, init=False)
    _reader_tasks: list[asyncio.Task[None]] = field(default_factory=list, init=False)

    @property
    def listen_uri(self) -> str:
        return f"ws://{self.host}:{self.port}"

    async def start(self) -> None:
        async def handler(conn: ServerConnection) -> None:
            try:
                async for raw in conn:
                    envelope = self._deserialize_envelope(raw)
                    if envelope is None:
                        continue
                    await self._accept_and_dispatch(envelope)
            except ConnectionClosed:
                logger.debug("Inbound connection closed for %s", self.node.peer_id)

        self._server = await websockets.serve(
            handler, self.host, self.port, max_size=self._MAX_MESSAGE_BYTES
        )
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
        existing = self._outgoing.get(uri)
        if existing is not None and existing.state == State.OPEN:
            return
        try:
            conn = await websockets.connect(uri, max_size=self._MAX_MESSAGE_BYTES)
        except OSError as exc:
            logger.warning("connect_to_peer failed %s: %s", uri, exc)
            raise
        self._outgoing[uri] = conn
        self._reader_tasks.append(asyncio.create_task(self._read_loop(conn, uri)))

    async def send(self, envelope: MeshEnvelope, peer_uri: str) -> None:
        await self.connect_to_peer(peer_uri)
        conn = self._outgoing[peer_uri]
        await conn.send(self._serialize_envelope(envelope))

    async def broadcast(self, envelope: MeshEnvelope) -> int:
        async def _do_send(uri: str) -> int:
            try:
                await self.send(envelope, uri)
                return 1
            except Exception:
                logger.warning("Broadcast failed from %s to %s", self.node.peer_id, uri, exc_info=True)
                return 0

        uris = list(self._outgoing.keys())
        if not uris:
            return 0
        results = await asyncio.gather(*[_do_send(uri) for uri in uris])
        return sum(results)

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

    async def _read_loop(self, conn: ClientConnection, uri: str) -> None:
        current_task = asyncio.current_task()
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
            if current_task is not None and current_task in self._reader_tasks:
                self._reader_tasks.remove(current_task)

    async def _accept_and_dispatch(self, envelope: MeshEnvelope) -> None:
        self._learn_origin_address(envelope)
        delivery_latency = self._latency_from_envelope(envelope)
        self._emit_delivery(envelope, delivery_latency, True)
        out = self.node.receive(envelope)
        if out:
            await self.send_many_routed(out)

    # Max allowed size of a single incoming WebSocket message (1 MB).
    _MAX_MESSAGE_BYTES = 1_048_576

    def _learn_origin_address(self, envelope: MeshEnvelope) -> None:
        origin_address = envelope.payload.get("origin_address")
        if not isinstance(origin_address, str):
            return
        # BUG-WS-02: Validate URI format strictly — accept only ws:// or wss:// on
        # an explicit host:port so an attacker cannot inject arbitrary addresses.
        import re as _re
        if not _re.fullmatch(r"wss?://[A-Za-z0-9._\-]+(:\d{1,5})?(/[^\s]*)?", origin_address):
            logger.warning(
                "Rejected suspicious origin_address %r from peer %s",
                origin_address,
                envelope.origin,
            )
            return
        if not self.node.registry.has(envelope.origin):
            self.node.add_peer(envelope.origin, origin_address)

    def _serialize_envelope(self, env: MeshEnvelope) -> str:
        payload = dict(env.payload)
        payload.setdefault("origin_address", self.listen_uri)
        payload.setdefault("transport_sent_at", time.time())
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

    def _deserialize_envelope(self, raw: str | bytes | bytearray) -> Optional[MeshEnvelope]:
        if isinstance(raw, (str, bytes, bytearray)) and len(raw) > self._MAX_MESSAGE_BYTES:
            unit = "chars" if isinstance(raw, str) else "bytes"
            logger.warning(
                "Dropped oversized message (%d %s) for node %s",
                len(raw),
                unit,
                self.node.peer_id,
            )
            return None
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

    def _latency_from_envelope(self, envelope: MeshEnvelope) -> float:
        sent_at = envelope.payload.get("transport_sent_at")
        if isinstance(sent_at, (int, float)):
            latency = max(0.0, time.time() - float(sent_at))
            return latency
        return 0.0

    def _emit_delivery(self, envelope: MeshEnvelope, latency_s: float, delivered_bool: bool) -> None:
        logger.info(
            "mesh_delivery node=%s env=%s origin=%s dest=%s latency_s=%.6f delivered=%s",
            self.node.peer_id,
            envelope.envelope_id,
            envelope.origin,
            envelope.destination,
            latency_s,
            delivered_bool,
        )
        if self.on_delivery is None:
            return
        self.on_delivery(
            DeliveryEvent(
                run=self.run_id,
                envelope_id=envelope.envelope_id,
                origin=envelope.origin,
                destination=envelope.destination,
                latency_s=latency_s,
                delivered_bool=delivered_bool,
            )
        )
