from __future__ import annotations

from dataclasses import dataclass, field
from collections import deque
from typing import Deque, Iterable, Optional, TypeVar, Generic

MessageT = TypeVar("MessageT")


class MeshBackpressureError(RuntimeError):
    pass


class MeshDisconnectedError(RuntimeError):
    pass


@dataclass(frozen=True)
class MeshRttConfig:
    max_queue: int = 32


@dataclass
class MeshRttSession(Generic[MessageT]):
    config: MeshRttConfig = field(default_factory=MeshRttConfig)
    _queue: Deque[MessageT] = field(default_factory=deque, init=False)
    _connected: bool = field(default=True, init=False)

    @property
    def connected(self) -> bool:
        return self._connected

    def send(self, message: MessageT) -> None:
        if not self._connected:
            raise MeshDisconnectedError("Mesh RTT disconnected")
        if len(self._queue) >= self.config.max_queue:
            raise MeshBackpressureError("Mesh RTT backpressure")
        self._queue.append(message)

    def send_batch(self, messages: Iterable[MessageT]) -> None:
        for message in messages:
            self.send(message)

    def receive(self) -> Optional[MessageT]:
        if not self._connected:
            raise MeshDisconnectedError("Mesh RTT disconnected")
        if not self._queue:
            return None
        return self._queue.popleft()

    def disconnect(self) -> None:
        self._connected = False

    def reconnect(self) -> None:
        self._connected = True
        self._queue.clear()
