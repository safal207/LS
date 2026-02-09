from __future__ import annotations

from dataclasses import dataclass, field
from collections import deque
from typing import Deque, Generic, Iterable, Optional, TypeVar


MessageT = TypeVar("MessageT")


class BackpressureError(RuntimeError):
    pass


class DisconnectedError(RuntimeError):
    pass


@dataclass(frozen=True)
class RttConfig:
    max_queue: int = 16
    reconnect_backoff_s: float = 0.1


@dataclass
class RttSession(Generic[MessageT]):
    config: RttConfig = field(default_factory=RttConfig)
    _queue: Deque[MessageT] = field(default_factory=deque, init=False)
    _connected: bool = field(default=True, init=False)
    reconnects: int = field(default=0, init=False)

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def pending(self) -> int:
        return len(self._queue)

    def send(self, message: MessageT) -> None:
        if not self._connected:
            raise DisconnectedError("RTT session is disconnected")
        if len(self._queue) >= self.config.max_queue:
            raise BackpressureError("RTT backpressure: queue is full")
        self._queue.append(message)

    def send_batch(self, messages: Iterable[MessageT]) -> None:
        for message in messages:
            self.send(message)

    def receive(self) -> Optional[MessageT]:
        if not self._connected:
            raise DisconnectedError("RTT session is disconnected")
        if not self._queue:
            return None
        return self._queue.popleft()

    def disconnect(self) -> None:
        self._connected = False

    def reconnect(self) -> None:
        if self._connected:
            return
        self._connected = True
        self._queue.clear()
        self.reconnects += 1
