from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Optional

from .observability import ObservabilityHub
from .transport import MessageT, TransportBackend, TransportFailover


@dataclass
class Web4Session(Generic[MessageT]):
    transport: TransportBackend[MessageT]
    observability: Optional[ObservabilityHub] = None
    backup_transport: Optional[TransportBackend[MessageT]] = None
    failover_threshold: int = 3

    def __post_init__(self) -> None:
        if self.backup_transport is not None:
            self.transport = TransportFailover(
                primary=self.transport,
                backup=self.backup_transport,
                failover_threshold=self.failover_threshold,
            )

    def connect(self) -> None:
        self.transport.connect()
        self._record("transport_connect")

    def disconnect(self) -> None:
        self.transport.disconnect()
        self._record("transport_disconnect")

    def send(self, message: MessageT, priority: int = 5) -> None:
        try:
            self.transport.send(message, priority=priority)  # type: ignore[call-arg]
        except TypeError:
            self.transport.send(message)
        self._record("transport_send", pending=self.transport.pending())

    def receive(self) -> Optional[MessageT]:
        item = self.transport.receive()
        if item is not None:
            self._record("transport_receive", pending=self.transport.pending())
        return item

    def pending(self) -> int:
        return self.transport.pending()

    def stats(self) -> object:
        return self.transport.stats()

    def heartbeat(self) -> None:
        self.transport.heartbeat()

    def check_heartbeat_timeout(self) -> bool:
        timed_out = self.transport.check_heartbeat_timeout()
        if timed_out:
            self._record("transport_heartbeat_timeout")
        return timed_out

    def _record(self, event_type: str, **payload: object) -> None:
        if self.observability is None:
            return
        self.observability.record(
            event_type,
            {
                "transport_type": self.transport.transport_type,
                **payload,
            },
        )
