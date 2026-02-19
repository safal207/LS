from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from time import monotonic
from typing import TYPE_CHECKING, Deque, Generic, Optional, TypeVar

from .fuzzy import smooth_coherence
from .rtt import BackpressureError, DisconnectedError, RttConfig, RttStats
from .rtt_queue import RttQueue

if TYPE_CHECKING:
    from .flow import GlobalFlowController

MessageT = TypeVar("MessageT")
_PRIORITY_QUEUE_COMPACTION_RATIO = 2


@dataclass(eq=False)
class AsyncRttSession(Generic[MessageT]):
    config: RttConfig = field(default_factory=RttConfig)
    flow_controller: Optional["GlobalFlowController[AsyncRttSession[MessageT]]"] = None
    _message_queue: RttQueue[MessageT] = field(init=False)
    _stats: RttStats = field(default_factory=RttStats, init=False)
    _connected: bool = field(default=True, init=False)
    _heartbeat_at: float = field(default_factory=monotonic, init=False)
    _condition: Optional[asyncio.Condition] = field(default=None, init=False)
    _condition_loop: Optional[asyncio.AbstractEventLoop] = field(default=None, init=False)
    _notify_tasks: set[asyncio.Task[None]] = field(default_factory=set, init=False)
    _coherence: float = field(default_factory=lambda: 1.0, init=False)

    def __post_init__(self) -> None:
        self._message_queue = RttQueue(
            enable_priority_queue=self.config.enable_priority_queue,
            backpressure_policy=self.config.backpressure_policy,
        )
        if self.flow_controller is not None:
            self.flow_controller.register_session(self)

    def _get_condition(self) -> asyncio.Condition:
        loop = asyncio.get_running_loop()
        if self._condition is None:
            self._condition = asyncio.Condition()
            self._condition_loop = loop
        elif self._condition_loop is not None and self._condition_loop is not loop:
            raise RuntimeError("AsyncRttSession condition must be used from a single event loop")
        return self._condition

    def _notify_global_space_available(self) -> None:
        condition = self._condition
        loop = self._condition_loop
        if condition is None or loop is None or loop.is_closed():
            return

        def _schedule_notify() -> None:
            async def _notify() -> None:
                async with condition:
                    condition.notify_all()

            task = loop.create_task(_notify())
            self._notify_tasks.add(task)
            task.add_done_callback(self._notify_tasks.discard)

        loop.call_soon_threadsafe(_schedule_notify)


    @property
    def coherence(self) -> float:
        return self._coherence

    async def update_lce_coherence(self, measured_coherence: float, *, drift: float = 0.0, noise: float = 0.0) -> float:
        new_coherence = smooth_coherence(self._coherence, measured_coherence, drift, noise)

        condition = self._get_condition()
        async with condition:
            self._coherence = new_coherence
            condition.notify_all()
        return new_coherence

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def pending(self) -> int:
        return self._message_queue.pending()

    @property
    def _queue(self) -> Deque[MessageT]:
        return self._message_queue.fifo

    @property
    def _priority_queue(self) -> list[tuple[int, int, MessageT]]:
        return self._message_queue.priority_heap

    @property
    def _priority_oldest_queue(self) -> list[tuple[int, int]]:
        return self._message_queue.oldest_heap

    @property
    def _live_priority_seq(self) -> set[int]:
        return self._message_queue.live_sequences

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
            self._message_queue.clear()
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
        self._message_queue.enqueue(message, priority)

    def _receive_unlocked(self) -> Optional[MessageT]:
        return self._message_queue.dequeue()

    async def _handle_overflow_async(self, *, is_global: bool, message: MessageT, priority: Optional[int]) -> None:
        self._bump(overflow_events=1)
        if self.config.backpressure_policy == "dropoldest":
            dropped = self._message_queue.drop_oldest()
            self._message_queue.maybe_compact(_PRIORITY_QUEUE_COMPACTION_RATIO)
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
                    if self.flow_controller.try_enqueue(self):
                        self._enqueue(message, priority)
                        self._bump(enqueued=1)
                        return
                elif is_global:
                    if self.pending < self.config.max_queue:
                        if self.flow_controller is None:
                            self._enqueue(message, priority)
                            self._bump(enqueued=1)
                            return
                        if self.flow_controller.try_enqueue(self):
                            if self.pending < self.config.max_queue:
                                self._enqueue(message, priority)
                                self._bump(enqueued=1)
                                return
                            self.flow_controller.on_dequeue(self)

                remaining = deadline - monotonic()
                if remaining <= 0:
                    break
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
        condition = self._get_condition()
        if not condition.locked():
            raise RuntimeError("AsyncRttSession._bump must run under condition lock")
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
