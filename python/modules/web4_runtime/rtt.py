from __future__ import annotations

from dataclasses import dataclass, field
from threading import Condition
from time import monotonic
from typing import TYPE_CHECKING, Any, Callable, Deque, Generic, Iterable, Optional, TypeVar

from .rtt_queue import BackpressurePolicy, RttQueue

_PRIORITY_QUEUE_COMPACTION_RATIO = 2

if TYPE_CHECKING:
    from .flow import GlobalFlowController
    from .observability import ObservabilityHub


MessageT = TypeVar("MessageT")
LifecycleHook = Callable[[int], None]


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
    session_id: int = 0
    heartbeat_timeout_s: float = 1.0
    enable_priority_queue: bool = False
    regulator_alpha_min: float = 0.2
    regulator_alpha_max: float = 0.5
    regulator_volatility_window: int = 100

    def __post_init__(self) -> None:
        if self.max_queue < 1:
            raise ValueError(f"RttConfig.max_queue must be >= 1, got {self.max_queue}")


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
    priority_inversions: int = 0
    high_priority_dropped: int = 0

    @property
    def accepted(self) -> int:
        return self.enqueued

    @property
    def dropped(self) -> int:
        return self.dropped_oldest + self.dropped_newest


@dataclass(eq=False)
class RttSession(Generic[MessageT]):
    config: RttConfig = field(default_factory=RttConfig)
    observability: Optional["ObservabilityHub"] = None
    flow_controller: Optional["GlobalFlowController[RttSession[MessageT]]"] = None
    _message_queue: RttQueue[MessageT] = field(init=False)
    _connected: bool = field(default=True, init=False)
    _stats: RttStats = field(default_factory=RttStats, init=False)
    _condition: Condition = field(default_factory=Condition, init=False)
    _heartbeat_at: float = field(default_factory=monotonic, init=False)
    _on_session_open: list[LifecycleHook] = field(default_factory=list, init=False)
    _on_session_close: list[LifecycleHook] = field(default_factory=list, init=False)
    _on_heartbeat_timeout: list[LifecycleHook] = field(default_factory=list, init=False)
    reconnects: int = field(default=0, init=False)
    _emitting: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self._message_queue = RttQueue(
            enable_priority_queue=self.config.enable_priority_queue,
            backpressure_policy=self.config.backpressure_policy,
        )
        if self.flow_controller is not None:
            self.flow_controller.register_session(self)

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

    def register_on_session_open(self, hook: LifecycleHook) -> None:
        with self._condition:
            self._on_session_open.append(hook)
            connected = self._connected
            session_id = self.config.session_id
        if connected:
            hook(session_id)

    def unregister_on_session_open(self, hook: LifecycleHook) -> None:
        with self._condition:
            if hook in self._on_session_open:
                self._on_session_open.remove(hook)

    def register_on_session_close(self, hook: LifecycleHook) -> None:
        with self._condition:
            self._on_session_close.append(hook)

    def unregister_on_session_close(self, hook: LifecycleHook) -> None:
        with self._condition:
            if hook in self._on_session_close:
                self._on_session_close.remove(hook)

    def register_on_heartbeat_timeout(self, hook: LifecycleHook) -> None:
        with self._condition:
            self._on_heartbeat_timeout.append(hook)

    def unregister_on_heartbeat_timeout(self, hook: LifecycleHook) -> None:
        with self._condition:
            if hook in self._on_heartbeat_timeout:
                self._on_heartbeat_timeout.remove(hook)

    def clear_session_hooks(self) -> None:
        with self._condition:
            self._on_session_open.clear()
            self._on_session_close.clear()
            self._on_heartbeat_timeout.clear()

    def send(self, message: MessageT, priority: Optional[int] = None) -> None:
        with self._condition:
            if not self._connected:
                self._bump(errors=1)
                raise DisconnectedError("RTT session is disconnected")
            self._bump(attempted=1)
            if self.pending >= self.config.max_queue:
                self._handle_overflow(is_global=False, message=message, priority=priority)
                return
            if self.flow_controller is not None and not self.flow_controller.try_enqueue(self):
                self._handle_overflow(is_global=True, message=message, priority=priority)
                return
            self._enqueue(message, priority)
            self._bump(enqueued=1)
            self._condition.notify_all()

    def _enqueue(self, message: MessageT, priority: Optional[int]) -> None:
        self._message_queue.enqueue(message, priority)

    def _handle_overflow(self, *, is_global: bool, message: MessageT, priority: Optional[int] = None) -> None:
        self._bump(overflow_events=1)
        if self.config.backpressure_policy == "dropoldest":
            actually_dropped = self._message_queue.drop_oldest()
            self._message_queue.maybe_compact(_PRIORITY_QUEUE_COMPACTION_RATIO)

            if not actually_dropped:
                self._bump(dropped_newest=1)
                return

            if self.flow_controller is not None:
                # Remove the evicted message from global accounting first.
                self.flow_controller.on_dequeue(self)
                # Re-acquire admission for the replacement message.
                if not self.flow_controller.try_enqueue(self):
                    self._bump(dropped_oldest=1)
                    self._condition.notify_all()
                    return

            self._enqueue(message, priority)
            self._bump(enqueued=1, dropped_oldest=1)
            self._condition.notify_all()
            return

        if self.config.backpressure_policy == "dropnewest":
            self._bump(dropped_newest=1)
            if priority is not None and priority >= 8:
                self._bump(high_priority_dropped=1)
            return

        if self.config.backpressure_policy == "block":
            self._bump(blocked=1)
            deadline = monotonic() + max(0.0, self.config.block_timeout_s)

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
                        if self.flow_controller.can_enqueue(self) and self.flow_controller.try_enqueue(self):
                            # Preserve local queue invariants even under concurrent global changes.
                            if self.pending < self.config.max_queue:
                                self._enqueue(message, priority)
                                self._bump(enqueued=1)
                                return
                            self.flow_controller.on_dequeue(self)

                remaining = max(0.0, deadline - monotonic())
                if remaining <= 0:
                    break
                self._condition.wait(timeout=min(remaining, 0.01))

            self._bump(errors=1)
            if not self._connected:
                raise DisconnectedError("RTT session is disconnected")
            raise BackpressureError("RTT backpressure: block timeout")

        self._bump(errors=1)
        raise BackpressureError("RTT backpressure: queue is full")

    def send_batch(self, messages: Iterable[MessageT]) -> None:
        for message in messages:
            self.send(message)

    def receive(self) -> Optional[MessageT]:
        with self._condition:
            if not self._connected:
                raise DisconnectedError("RTT session is disconnected")
            item = self._message_queue.dequeue()
            if item is None:
                return None
            if self.flow_controller is not None:
                self.flow_controller.on_dequeue(self)
            self._condition.notify_all()
            return item

    def heartbeat(self) -> None:
        with self._condition:
            self._heartbeat_at = monotonic()

    def check_heartbeat_timeout(self) -> bool:
        with self._condition:
            if not self._connected:
                return False
            timed_out = monotonic() - self._heartbeat_at >= max(0.0, self.config.heartbeat_timeout_s)
            if not timed_out:
                return False
            self._connected = False
            self._condition.notify_all()
            timeout_hooks = list(self._on_heartbeat_timeout)
            close_hooks = list(self._on_session_close)
        self._emit("heartbeat_timeout", timeout_hooks)
        self._emit("session_close", close_hooks, reason="heartbeat_timeout")
        return True

    def disconnect(self, reason: str = "manual") -> None:
        with self._condition:
            if not self._connected:
                return
            self._connected = False
            self._condition.notify_all()
            close_hooks = list(self._on_session_close)
        self._emit("session_close", close_hooks, reason=reason)

    def reconnect(self) -> None:
        with self._condition:
            if self._connected:
                return
            self._connected = True
            self._message_queue.clear()
            self._heartbeat_at = monotonic()
            if self.flow_controller is not None:
                self.flow_controller.on_reset(self)
            self.reconnects += 1
            reconnects = self.reconnects
            self._condition.notify_all()
            open_hooks = list(self._on_session_open)
        self._emit("session_open", open_hooks, reconnects=reconnects)

    def _emit(self, event_type: str, hooks: list[LifecycleHook], **metadata: Any) -> None:
        with self._condition:
            if self._emitting:
                return
            self._emitting = True
        try:
            if self.observability is not None:
                self.observability.record(
                    event_type,
                    {"session_id": self.config.session_id, **metadata},
                )
            for hook in hooks:
                hook(self.config.session_id)
        finally:
            with self._condition:
                self._emitting = False

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
