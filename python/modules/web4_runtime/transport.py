from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import cast
from typing import Generic, Optional, Protocol, TypeVar

from .rtt import RttSession, RttStats


MessageT = TypeVar("MessageT")


class TransportBackend(Protocol, Generic[MessageT]):
    @property
    def transport_type(self) -> str: ...

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


@dataclass
class TransportFailover(Generic[MessageT]):
    primary: TransportBackend[MessageT]
    backup: TransportBackend[MessageT]
    failover_threshold: int = 3
    recovery_check_interval_s: int = 30
    recovery_success_threshold: int = 5
    _error_count: int = field(default=0, init=False)
    _using_backup: bool = field(default=False, init=False)
    _failover_count: int = field(default=0, init=False)
    _recovery_success_count: int = field(default=0, init=False)
    _last_recovery_check: float = field(default=0.0, init=False)

    @property
    def transport_type(self) -> str:
        return f"failover:{self.current_transport.transport_type}"

    @property
    def current_transport(self) -> TransportBackend[MessageT]:
        return self.backup if self._using_backup else self.primary

    def connect(self) -> None:
        self.primary.connect()
        self.backup.connect()
        self._using_backup = False
        self._error_count = 0
        self._recovery_success_count = 0
        self._last_recovery_check = monotonic()

    def disconnect(self) -> None:
        self.primary.disconnect()
        self.backup.disconnect()

    def send(self, message: MessageT) -> None:
        try:
            self.current_transport.send(message)
            self._error_count = 0

            if self._using_backup:
                self._recovery_success_count += 1
                now = monotonic()
                if (
                    self._recovery_success_count >= self.recovery_success_threshold
                    and now - self._last_recovery_check >= max(0, self.recovery_check_interval_s)
                ):
                    self._attempt_recovery()
                    self._last_recovery_check = now
        except Exception:
            self._error_count += 1
            if self._error_count >= self.failover_threshold and not self._using_backup:
                self._using_backup = True
                self._error_count = 0
                self._failover_count += 1
                self.backup.connect()
            raise

    def receive(self) -> Optional[MessageT]:
        return self.current_transport.receive()

    def pending(self) -> int:
        return self.current_transport.pending()

    def stats(self) -> object:
        return {
            "using_backup": self._using_backup,
            "failover_count": self._failover_count,
            "error_count": self._error_count,
            "recovery_success_count": self._recovery_success_count,
            "active_transport": self.current_transport.transport_type,
            "active_stats": self.current_transport.stats(),
        }

    def heartbeat(self) -> None:
        self.current_transport.heartbeat()

    def check_heartbeat_timeout(self) -> bool:
        return self.current_transport.check_heartbeat_timeout()

    def _attempt_recovery(self) -> None:
        try:
            self.primary.connect()
            self.primary.send(cast(MessageT, "__recovery_test__"))
            self._using_backup = False
            self._recovery_success_count = 0
            self._error_count = 0
        except Exception:
            return
