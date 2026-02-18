from __future__ import annotations

import asyncio
import heapq
from collections import deque
from dataclasses import dataclass, field
from time import monotonic
from typing import TYPE_CHECKING, Deque, Generic, Optional, TypeVar

from .rtt import BackpressureError, DisconnectedError, RttConfig, RttStats

if TYPE_CHECKING:
    from .flow import GlobalFlowController

MessageT = TypeVar("MessageT")
_PRIORITY_QUEUE_COMPACTION_RATIO = 2


@dataclass
class AsyncRttSession(Generic[MessageT]):
    config: RttConfig = field(default_factory=RttConfig)
    flow_controller: Optional["GlobalFlowController[AsyncRttSession[MessageT]]"] = None
    _queue: Deque[MessageT] = field(default_factory=deque, init=False)
    _priority_queue: list[tuple[int, int, MessageT]] = field(default_factory=list, init=False)
    _priority_oldest_queue: list[tuple[int, int]] = field(default_factory=list, init=False)
    _priority_seq: int = field(default=0, init=False)
    _live_priority_seq: set[int] = field(default_factory=set, init=False)
    _stats: RttStats = field(default_factory=RttStats, init=False)
    _connected: bool = field(default=True, init=False)
    _heartbeat_at: float = field(default_factory=monotonic, init=False)
    _condition: Optional[asyncio.Condition] = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.flow_controller is not None:
            self.flow_controller.register_session(self)

    def _get_condition(self) -> asyncio.Condition:
        if self._condition is None:
            self._condition = asyncio.Condition()
        return self._condition

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def pending(self) -> int:
        if self.config.enable_priority_queue:
            return len(self._queue) + len(self._live_priority_seq)
        return len(self._queue)

    @property
    def stats(self) -> RttStats:
        return self._stats

    async def send_async(self, message: MessageT, priority: Optional[int] = None) -> None:
        condition = self._get_condition()
        async with condition:
            if not self._connected:
                self._bump(errors=1)
                raise DisconnectedError("RTT session is disconnected")

            self._bump(attempted=1)
            if self.pending >= self.config.max_queue:
                await self._handle_overflow_async(is_global=False, message=message, priority=priority)
            elif self.flow_controller is not None and not self.flow_controller.try_enqueue(self):
                await self._handle_overflow_async(is_global=True, message=message, priority=priority)
            else:
                self._enqueue(message, priority)
                self._bump(enqueued=1)
            condition.notify_all()

    async def receive_async(self) -> Optional[MessageT]:
        condition = self._get_condition()
        notify_flow = False
        item: Optional[MessageT] = None
        async with condition:
            if not self._connected:
                raise DisconnectedError("RTT session is disconnected")
            item = self._receive_unlocked()
            if item is not None and self.flow_controller is not None:
                self.flow_controller.on_dequeue(self)
                notify_flow = True
            if item is not None:
                condition.notify_all()
        if notify_flow and self.flow_controller is not None:
            await self.flow_controller.notify_available_space()
        return item

    async def wait_message(self, timeout_s: float = 1.0) -> Optional[MessageT]:
        deadline = monotonic() + max(0.0, timeout_s)
        condition = self._get_condition()
        notify_flow = False
        item: Optional[MessageT] = None
        async with condition:
            while True:
                if not self._connected:
                    raise DisconnectedError("RTT session is disconnected")

                item = self._receive_unlocked()
                if item is not None:
                    if self.flow_controller is not None:
                        self.flow_controller.on_dequeue(self)
                        notify_flow = True
                    condition.notify_all()
                    break

                remaining = deadline - monotonic()
                if remaining <= 0:
                    return None
                try:
                    await asyncio.wait_for(condition.wait(), timeout=remaining)
                except asyncio.TimeoutError:
                    return None
        if notify_flow and self.flow_controller is not None:
            await self.flow_controller.notify_available_space()
        return item

    async def disconnect(self) -> None:
        condition = self._get_condition()
        async with condition:
            self._connected = False
            condition.notify_all()

    async def reconnect(self) -> None:
        condition = self._get_condition()
        async with condition:
            self._connected = True
            self._queue.clear()
            self._priority_queue.clear()
            self._priority_oldest_queue.clear()
            self._live_priority_seq.clear()
            self._heartbeat_at = monotonic()
            if self.flow_controller is not None:
                self.flow_controller.on_reset(self)
            condition.notify_all()

    async def heartbeat(self) -> None:
        condition = self._get_condition()
        async with condition:
            self._heartbeat_at = monotonic()

    async def check_heartbeat_timeout(self) -> bool:
        condition = self._get_condition()
        async with condition:
            if not self._connected:
                return False
            timed_out = monotonic() - self._heartbeat_at >= max(0.0, self.config.heartbeat_timeout_s)
            if not timed_out:
                return False
            self._connected = False
            condition.notify_all()
            return True

    def _enqueue(self, message: MessageT, priority: Optional[int]) -> None:
        if self.config.enable_priority_queue:
            self._priority_seq += 1
            normalized_priority = priority if priority is not None else 0
            heapq.heappush(self._priority_queue, (-normalized_priority, self._priority_seq, message))
            if self.config.backpressure_policy == "dropoldest":
                heapq.heappush(self._priority_oldest_queue, (self._priority_seq, -normalized_priority))
            self._live_priority_seq.add(self._priority_seq)
            return
        self._queue.append(message)

    def _drop_oldest_priority(self) -> bool:
        while self._priority_oldest_queue:
            sequence, _ = heapq.heappop(self._priority_oldest_queue)
            if sequence in self._live_priority_seq:
                self._live_priority_seq.remove(sequence)
                return True
        return False

    def _maybe_compact_priority_queue(self) -> None:
        if not self._priority_queue:
            return
        stale_count = len(self._priority_queue) - len(self._live_priority_seq)
        if stale_count <= len(self._live_priority_seq) * _PRIORITY_QUEUE_COMPACTION_RATIO:
            return
        self._priority_queue = [entry for entry in self._priority_queue if entry[1] in self._live_priority_seq]
        heapq.heapify(self._priority_queue)

    def _receive_unlocked(self) -> Optional[MessageT]:
        if self.config.enable_priority_queue:
            while self._priority_queue:
                _, sequence, item = heapq.heappop(self._priority_queue)
                if sequence in self._live_priority_seq:
                    self._live_priority_seq.remove(sequence)
                    return item
            return None
        if not self._queue:
            return None
        return self._queue.popleft()

    async def _handle_overflow_async(self, *, is_global: bool, message: MessageT, priority: Optional[int]) -> None:
        self._bump(overflow_events=1)
        if self.config.backpressure_policy == "dropoldest":
            dropped = False
            if self.config.enable_priority_queue:
                dropped = self._drop_oldest_priority()
                if not dropped and self._queue:
                    self._queue.popleft()
                    dropped = True
                self._maybe_compact_priority_queue()
            elif self._queue:
                self._queue.popleft()
                dropped = True
            if not dropped:
                self._bump(dropped_newest=1)
                return
            if self.flow_controller is not None:
                # Eviction frees one global slot; replacement must reacquire.
                self.flow_controller.on_dequeue(self)
                if not self.flow_controller.try_enqueue(self):
                    self._bump(dropped_oldest=1)
                    self._get_condition().notify_all()
                    return
            self._enqueue(message, priority)
            self._bump(enqueued=1, dropped_oldest=1)
            self._get_condition().notify_all()
            return
        if self.config.backpressure_policy == "dropnewest":
            self._bump(dropped_newest=1)
            return
        if self.config.backpressure_policy == "block":
            self._bump(blocked=1)
            deadline = monotonic() + max(0.0, self.config.block_timeout_s)
            condition = self._get_condition()
            while self._connected:
                if not is_global and self.pending < self.config.max_queue:
                    if self.flow_controller is None:
                        self._enqueue(message, priority)
                        self._bump(enqueued=1)
                        return
                    if self.flow_controller.can_enqueue(self) and self.flow_controller.try_enqueue(self):
                        self._enqueue(message, priority)
                        self._bump(enqueued=1)
                        return
                elif is_global:
                    if self.pending < self.config.max_queue:
                        if self.flow_controller is None:
                            self._enqueue(message, priority)
                            self._bump(enqueued=1)
                            return
                        if self.flow_controller.can_enqueue(self) and self.flow_controller.try_enqueue(self):
                            if self.pending < self.config.max_queue:
                                self._enqueue(message, priority)
                                self._bump(enqueued=1)
                                return
                            self.flow_controller.on_dequeue(self)

                remaining = deadline - monotonic()
                if remaining <= 0:
                    break
                if is_global and self.flow_controller is not None:
                    # Wait on global free-slot notifications without polling.
                    condition.release()
                    try:
                        woke = await self.flow_controller.wait_for_available_space(remaining)
                    finally:
                        await condition.acquire()
                    if not woke:
                        break
                else:
                    try:
                        await asyncio.wait_for(condition.wait(), timeout=remaining)
                    except asyncio.TimeoutError:
                        break
            self._bump(errors=1)
            if not self._connected:
                raise DisconnectedError("RTT session is disconnected")
            raise BackpressureError("RTT backpressure: block timeout")
        self._bump(errors=1)
        raise BackpressureError("RTT backpressure: queue is full")

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
        self._stats = RttStats(
            attempted=current.attempted + attempted,
            enqueued=current.enqueued + enqueued,
            dropped_oldest=current.dropped_oldest + dropped_oldest,
            dropped_newest=current.dropped_newest + dropped_newest,
            blocked=current.blocked + blocked,
            errors=current.errors + errors,
            overflow_events=current.overflow_events + overflow_events,
            max_queue_len=max(current.max_queue_len, self.pending),
            priority_inversions=current.priority_inversions + priority_inversions,
            high_priority_dropped=current.high_priority_dropped + high_priority_dropped,
        )
