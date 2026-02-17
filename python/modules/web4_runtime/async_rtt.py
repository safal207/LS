from __future__ import annotations

import asyncio
import heapq
from collections import deque
from dataclasses import dataclass, field
from time import monotonic
from typing import Deque, Generic, Optional, TypeVar

from .rtt import BackpressureError, DisconnectedError, RttConfig, RttStats

MessageT = TypeVar("MessageT")


@dataclass
class AsyncRttSession(Generic[MessageT]):
    config: RttConfig
    _queue: Deque[MessageT] = field(default_factory=deque, init=False)
    _priority_queue: list[tuple[int, int, MessageT]] = field(default_factory=list, init=False)
    _priority_oldest_queue: list[tuple[int, int]] = field(default_factory=list, init=False)
    _priority_seq: int = field(default=0, init=False)
    _live_priority_seq: set[int] = field(default_factory=set, init=False)
    _connected: bool = field(default=True, init=False)
    _stats: RttStats = field(default_factory=RttStats, init=False)
    _condition: asyncio.Condition = field(default_factory=asyncio.Condition, init=False)

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def pending(self) -> int:
        if self.config.enable_priority_queue:
            return len(self._live_priority_seq) + len(self._queue)
        return len(self._queue)

    @property
    def stats(self) -> RttStats:
        return self._stats

    async def send_async(self, message: MessageT, priority: Optional[int] = None) -> None:
        async with self._condition:
            if not self._connected:
                self._bump(errors=1)
                raise DisconnectedError("AsyncRttSession disconnected")
            self._bump(attempted=1)

            if self.pending >= self.config.max_queue:
                await self._on_overflow_async(message, priority)
                return

            self._enqueue(message, priority)
            self._bump(enqueued=1)
            self._condition.notify_all()

    async def receive_async(self) -> Optional[MessageT]:
        async with self._condition:
            if not self._connected:
                return None
            if self.config.enable_priority_queue:
                while self._priority_queue:
                    _, seq, item = heapq.heappop(self._priority_queue)
                    if seq in self._live_priority_seq:
                        self._live_priority_seq.remove(seq)
                        self._condition.notify_all()
                        return item
                return None
            if not self._queue:
                return None
            item = self._queue.popleft()
            self._condition.notify_all()
            return item

    async def wait_message(self, timeout_s: float = 0.1) -> Optional[MessageT]:
        deadline = monotonic() + max(0.0, timeout_s)
        while monotonic() < deadline:
            item = await self.receive_async()
            if item is not None:
                return item
            async with self._condition:
                remaining = max(0.0, deadline - monotonic())
                if remaining == 0.0:
                    break
                try:
                    await asyncio.wait_for(self._condition.wait(), timeout=remaining)
                except asyncio.TimeoutError:
                    break
        return None

    def disconnect(self) -> None:
        self._connected = False

    def _enqueue(self, message: MessageT, priority: Optional[int]) -> None:
        if self.config.enable_priority_queue or priority is not None:
            self._priority_seq += 1
            normalized_priority = priority if priority is not None else 0
            heapq.heappush(self._priority_queue, (-normalized_priority, self._priority_seq, message))
            if self.config.backpressure_policy == "dropoldest":
                heapq.heappush(self._priority_oldest_queue, (self._priority_seq, -normalized_priority))
            self._live_priority_seq.add(self._priority_seq)
            return
        self._queue.append(message)

    async def _on_overflow_async(self, message: MessageT, priority: Optional[int]) -> None:
        self._bump(overflow_events=1)
        if self.config.backpressure_policy == "dropoldest":
            if self.config.enable_priority_queue or priority is not None:
                self._drop_oldest_priority()
            elif self._queue:
                self._queue.popleft()
            self._enqueue(message, priority)
            self._bump(enqueued=1, dropped_oldest=1)
            return
        if self.config.backpressure_policy == "dropnewest":
            self._bump(dropped_newest=1)
            return
        if self.config.backpressure_policy == "block":
            self._bump(blocked=1)
            timeout = max(0.0, self.config.block_timeout_s)
            try:
                await asyncio.wait_for(
                    self._condition.wait_for(lambda: (not self._connected) or self.pending < self.config.max_queue),
                    timeout=timeout,
                )
            except asyncio.TimeoutError as exc:
                self._bump(errors=1)
                raise BackpressureError("RTT backpressure: block timeout") from exc

            if not self._connected:
                self._bump(errors=1)
                raise DisconnectedError("AsyncRttSession disconnected")
            self._enqueue(message, priority)
            self._bump(enqueued=1)
            return
        self._bump(errors=1)
        raise BackpressureError("RTT backpressure: queue is full")

    def _drop_oldest_priority(self) -> bool:
        while self._priority_oldest_queue:
            sequence, _ = heapq.heappop(self._priority_oldest_queue)
            if sequence in self._live_priority_seq:
                self._live_priority_seq.remove(sequence)
                return True
        return False

    def set_backpressure_policy(self, policy: str) -> None:
        self.config = RttConfig(
            max_queue=self.config.max_queue,
            reconnect_backoff_s=self.config.reconnect_backoff_s,
            backpressure_policy=policy,  # type: ignore[arg-type]
            block_timeout_s=self.config.block_timeout_s,
            session_id=self.config.session_id,
            heartbeat_timeout_s=self.config.heartbeat_timeout_s,
            enable_priority_queue=self.config.enable_priority_queue,
            regulator_alpha_min=self.config.regulator_alpha_min,
            regulator_alpha_max=self.config.regulator_alpha_max,
            regulator_volatility_window=self.config.regulator_volatility_window,
        )

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
        priority_inversions: int = 0,
        high_priority_dropped: int = 0,
    ) -> None:
        current = self._stats
        max_queue_len = max(current.max_queue_len, self.pending)
        self._stats = RttStats(
            attempted=current.attempted + attempted,
            enqueued=current.enqueued + enqueued,
            dropped_oldest=current.dropped_oldest + dropped_oldest,
            dropped_newest=current.dropped_newest + dropped_newest,
            blocked=current.blocked + blocked,
            errors=current.errors + errors,
            overflow_events=current.overflow_events + overflow_events,
            max_queue_len=max_queue_len,
            priority_inversions=current.priority_inversions + priority_inversions,
            high_priority_dropped=current.high_priority_dropped + high_priority_dropped,
        )
