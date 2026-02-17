from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from threading import Condition
from time import monotonic
from typing import TYPE_CHECKING, Any, Callable, Deque, Generic, Iterable, Literal, Optional, TypeVar

if TYPE_CHECKING:
    from .observability import ObservabilityHub


MessageT = TypeVar("MessageT")
BackpressurePolicy = Literal["dropoldest", "dropnewest", "block", "error"]
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


@dataclass
class RttSession(Generic[MessageT]):
    config: RttConfig = field(default_factory=RttConfig)
    observability: Optional["ObservabilityHub"] = None
    _queue: Deque[MessageT] = field(default_factory=deque, init=False)
    _priority_queue: Deque[tuple[int, MessageT]] = field(default_factory=deque, init=False)
    _connected: bool = field(default=True, init=False)
    _stats: RttStats = field(default_factory=RttStats, init=False)
    _condition: Condition = field(default_factory=Condition, init=False)
    _heartbeat_at: float = field(default_factory=monotonic, init=False)
    _on_session_open: list[LifecycleHook] = field(default_factory=list, init=False)
    _on_session_close: list[LifecycleHook] = field(default_factory=list, init=False)
    _on_heartbeat_timeout: list[LifecycleHook] = field(default_factory=list, init=False)
    reconnects: int = field(default=0, init=False)
    _emitting: bool = field(default=False, init=False)

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def pending(self) -> int:
        return len(self._priority_queue) if self.config.enable_priority_queue else len(self._queue)

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

    def send(self, message: MessageT, priority: int = 5) -> None:
        with self._condition:
            if not self._connected:
                self._bump(errors=1)
                raise DisconnectedError("RTT session is disconnected")
            self._bump(attempted=1)
            if self.config.enable_priority_queue:
                if len(self._priority_queue) >= self.config.max_queue:
                    self._on_overflow(message, priority)
                    return
                self._enqueue_priority(message, priority)
            else:
                if len(self._queue) >= self.config.max_queue:
                    self._on_overflow(message, priority)
                    return
                self._queue.append(message)
                self._bump(enqueued=1)
            self._condition.notify_all()

    def _enqueue_priority(self, message: MessageT, priority: int) -> None:
        inserted = False
        for index, (existing_priority, _) in enumerate(self._priority_queue):
            if priority > existing_priority:
                self._priority_queue.insert(index, (priority, message))
                inserted = True
                break
        if not inserted:
            self._priority_queue.append((priority, message))
        self._bump(enqueued=1)

    def _on_overflow(self, message: MessageT, priority: int = 5) -> None:
        self._bump(overflow_events=1)
        if self.config.backpressure_policy == "dropoldest":
            if self.config.enable_priority_queue:
                self._priority_queue.popleft()
                self._enqueue_priority(message, priority)
                if priority >= 8:
                    self._bump(high_priority_dropped=0)
            else:
                self._queue.popleft()
                self._queue.append(message)
                self._bump(enqueued=1)
            self._bump(dropped_oldest=1)
            return
        if self.config.backpressure_policy == "dropnewest":
            self._bump(dropped_newest=1)
            if self.config.enable_priority_queue and priority >= 8:
                self._bump(high_priority_dropped=1)
            return
        if self.config.backpressure_policy == "block":
            self._bump(blocked=1)
            deadline = monotonic() + max(0.0, self.config.block_timeout_s)

            def can_enqueue() -> bool:
                return (not self._connected) or (len(self._priority_queue if self.config.enable_priority_queue else self._queue) < self.config.max_queue)

            remaining = max(0.0, deadline - monotonic())
            ok = self._condition.wait_for(can_enqueue, timeout=remaining)
            if not ok or not self._connected:
                self._bump(errors=1)
                if not self._connected:
                    raise DisconnectedError("RTT session is disconnected")
                raise BackpressureError("RTT backpressure: block timeout")

            if self.config.enable_priority_queue:
                self._enqueue_priority(message, priority)
            else:
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
            if self.config.enable_priority_queue:
                if not self._priority_queue:
                    return None
                _, item = self._priority_queue.popleft()
            else:
                if not self._queue:
                    return None
                item = self._queue.popleft()
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
            self._queue.clear()
            self._priority_queue.clear()
            self._heartbeat_at = monotonic()
            self.reconnects += 1
            reconnects = self.reconnects
            self._condition.notify_all()
            open_hooks = list(self._on_session_open)
        self._emit("session_open", open_hooks, reconnects=reconnects)

    def _emit(self, event_type: str, hooks: list[LifecycleHook], **metadata: Any) -> None:
        # Re-entrancy guard for nested lifecycle callbacks (thread-safe under condition lock).
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
        queue_len = len(self._priority_queue) if self.config.enable_priority_queue else len(self._queue)
        max_queue_len = max(current.max_queue_len, queue_len)
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
