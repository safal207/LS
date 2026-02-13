from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from threading import Condition
from time import monotonic
from typing import Deque, Generic, Iterable, Literal, Optional, TypeVar


MessageT = TypeVar("MessageT")
BackpressurePolicy = Literal["dropoldest", "dropnewest", "block", "error"]


class BackpressureError(RuntimeError):
    pass


class DisconnectedError(RuntimeError):
    pass


@dataclass(frozen=True)
class RttConfig:
    max_queue: int = 16
    reconnect_backoff_s: float = 0.1
    backpressure_policy: BackpressurePolicy = "error"
    block_timeout_s: float = 0.1


@dataclass(frozen=True)
class RttStats:
    attempted: int = 0
    enqueued: int = 0
    dropped_oldest: int = 0
    dropped_newest: int = 0
    blocked: int = 0
    errors: int = 0
    overflow_events: int = 0
    max_queue_len: int = 0

    @property
    def accepted(self) -> int:
        return self.enqueued

    @property
    def dropped(self) -> int:
        return self.dropped_oldest + self.dropped_newest


@dataclass
class RttSession(Generic[MessageT]):
    config: RttConfig = field(default_factory=RttConfig)
    _queue: Deque[MessageT] = field(default_factory=deque, init=False)
    _connected: bool = field(default=True, init=False)
    _stats: RttStats = field(default_factory=RttStats, init=False)
    _condition: Condition = field(default_factory=Condition, init=False)
    reconnects: int = field(default=0, init=False)

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def pending(self) -> int:
        return len(self._queue)

    @property
    def stats(self) -> RttStats:
        return self._stats

    def send(self, message: MessageT) -> None:
        with self._condition:
            if not self._connected:
                self._bump(errors=1)
                raise DisconnectedError("RTT session is disconnected")
            self._bump(attempted=1)
            if len(self._queue) >= self.config.max_queue:
                self._on_overflow(message)
                return
            self._queue.append(message)
            self._bump(enqueued=1)
            self._condition.notify_all()

    def _on_overflow(self, message: MessageT) -> None:
        self._bump(overflow_events=1)
        if self.config.backpressure_policy == "dropoldest":
            self._queue.popleft()
            self._queue.append(message)
            self._bump(enqueued=1, dropped_oldest=1)
            return
        if self.config.backpressure_policy == "dropnewest":
            self._bump(dropped_newest=1)
            return
        if self.config.backpressure_policy == "block":
            self._bump(blocked=1)
            deadline = monotonic() + max(0.0, self.config.block_timeout_s)
            while len(self._queue) >= self.config.max_queue and self._connected:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    self._bump(errors=1)
                    raise BackpressureError("RTT backpressure: block timeout")
                self._condition.wait(timeout=remaining)
            if not self._connected:
                self._bump(errors=1)
                raise DisconnectedError("RTT session is disconnected")
            self._queue.append(message)
            self._bump(enqueued=1)
            return
        self._bump(errors=1)
        raise BackpressureError("RTT backpressure: queue is full")

    def send_batch(self, messages: Iterable[MessageT]) -> None:
        for message in messages:
            self.send(message)

    def receive(self) -> Optional[MessageT]:
        with self._condition:
            if not self._connected:
                raise DisconnectedError("RTT session is disconnected")
            if not self._queue:
                return None
            item = self._queue.popleft()
            self._condition.notify_all()
            return item

    def disconnect(self) -> None:
        with self._condition:
            self._connected = False
            self._condition.notify_all()

    def reconnect(self) -> None:
        with self._condition:
            if self._connected:
                return
            self._connected = True
            self._queue.clear()
            self.reconnects += 1
            self._condition.notify_all()

    def _bump(
        self,
        *,
        attempted: int = 0,
        enqueued: int = 0,
        dropped_oldest: int = 0,
        dropped_newest: int = 0,
        blocked: int = 0,
        errors: int = 0,
        overflow_events: int = 0,
    ) -> None:
        current = self._stats
        max_queue_len = max(current.max_queue_len, len(self._queue))
        self._stats = RttStats(
            attempted=current.attempted + attempted,
            enqueued=current.enqueued + enqueued,
            dropped_oldest=current.dropped_oldest + dropped_oldest,
            dropped_newest=current.dropped_newest + dropped_newest,
            blocked=current.blocked + blocked,
            errors=current.errors + errors,
            overflow_events=current.overflow_events + overflow_events,
            max_queue_len=max_queue_len,
        )
