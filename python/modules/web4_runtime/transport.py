from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Optional, Protocol, TypeVar

from .rtt import RttSession, RttStats


MessageT = TypeVar("MessageT")


class TransportBackend(Protocol, Generic[MessageT]):
    transport_type: str

    def connect(self) -> None: ...

    def disconnect(self) -> None: ...

    def send(self, message: MessageT) -> None: ...

    def receive(self) -> Optional[MessageT]: ...

    def pending(self) -> int: ...

    def stats(self) -> object: ...

    def heartbeat(self) -> None: ...

    def check_heartbeat_timeout(self) -> bool: ...


@dataclass
class RttTransport(Generic[MessageT]):
    session: RttSession[MessageT]
    transport_type: str = "rtt"

    def connect(self) -> None:
        self.session.reconnect()

    def disconnect(self) -> None:
        self.session.disconnect()

    def send(self, message: MessageT) -> None:
        self.session.send(message)

    def receive(self) -> Optional[MessageT]:
        return self.session.receive()

    def pending(self) -> int:
        return self.session.pending

    def stats(self) -> RttStats:
        return self.session.stats

    def heartbeat(self) -> None:
        self.session.heartbeat()

    def check_heartbeat_timeout(self) -> bool:
        return self.session.check_heartbeat_timeout()
