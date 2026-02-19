from __future__ import annotations

import asyncio
from time import monotonic
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Condition, RLock
from typing import Callable, Generic, Iterator, Literal, TypeVar

from .fuzzy import tune_backpressure_limits
from weakref import WeakKeyDictionary

SessionT = TypeVar("SessionT")
BackpressureStrategy = Literal["fixed", "proportional", "fuzzy"]


@dataclass
class GlobalFlowController(Generic[SessionT]):
    """Thread-safe global admission controller shared across RTT sessions."""

    total_limit: int = 10_000
    per_session_limit: int = 1_000
    strategy: BackpressureStrategy = "fixed"
    _session_pending: WeakKeyDictionary[object, int] = field(default_factory=WeakKeyDictionary, init=False)
    # Fallback path for non-weakrefable session objects.
    _strong_pending: dict[int, int] = field(default_factory=dict, init=False)
    _strong_sessions: dict[int, object] = field(default_factory=dict, init=False)
    _total_pending: int = field(default=0, init=False)
    _lock: RLock = field(default_factory=RLock, init=False)
    _space_available: Condition = field(init=False)
    _async_space_event: asyncio.Event | None = field(default=None, init=False)
    _async_loop: asyncio.AbstractEventLoop | None = field(default=None, init=False)
    _space_epoch: int = field(default=0, init=False)
    _fuzzy_per_session_limit: int = field(default=0, init=False)
    _fuzzy_total_limit: int = field(default=0, init=False)
    _last_fuzzy_update: float = field(default=0.0, init=False)
    _last_fuzzy_window_reset: float = field(default=0.0, init=False)
    _attempted_recent: int = field(default=0, init=False)
    _dropped_recent: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self._space_available = Condition(self._lock)
        self._fuzzy_per_session_limit = self.per_session_limit
        self._fuzzy_total_limit = self.total_limit
        now = monotonic()
        self._last_fuzzy_update = now
        self._last_fuzzy_window_reset = now

    @property
    def total_pending(self) -> int:
        with self._lock:
            self._refresh_total_pending_locked()
            return self._total_pending

    @property
    def active_sessions(self) -> int:
        with self._lock:
            return len(self._session_pending) + len(self._strong_pending)

    def _weak_pending_values_unlocked(self) -> tuple[int, ...]:
        return tuple(self._session_pending.values())

    def _total_pending_unlocked(self) -> int:
        attempts = 0
        while attempts < 3:
            try:
                weak_values = self._weak_pending_values_unlocked()
                return sum(weak_values) + sum(self._strong_pending.values())
            except RuntimeError:
                attempts += 1
        # Preserve last stable value rather than collapsing to a false zero.
        return self._total_pending

    def _notify_async_space_available(self) -> None:
        if self._async_space_event is None:
            return
        self._async_space_event.set()

    def _notify_available_space_locked(self) -> None:
        self._space_epoch += 1
        self._space_available.notify_all()
        loop = self._async_loop
        if loop is None or loop.is_closed() or self._async_space_event is None:
            return
        loop.call_soon_threadsafe(self._notify_async_space_available)

    def _ensure_async_event(self) -> asyncio.Event:
        loop = asyncio.get_running_loop()
        if self._async_space_event is None:
            self._async_space_event = asyncio.Event()
            self._async_loop = loop
            return self._async_space_event
        if self._async_loop is None:
            self._async_loop = loop
            return self._async_space_event
        if self._async_loop is not loop:
            raise RuntimeError("GlobalFlowController async waiters must run on a single event loop")
        return self._async_space_event

    async def notify_available_space(self) -> None:
        event = self._ensure_async_event()
        event.set()

    def current_space_epoch(self) -> int:
        return self._space_epoch

    async def wait_for_available_space(self, timeout_s: float, *, after_epoch: int | None = None) -> bool:
        event = self._ensure_async_event()
        timeout_s = max(0.0, timeout_s)
        if after_epoch is not None and self._space_epoch != after_epoch:
            return True

        deadline = asyncio.get_running_loop().time() + timeout_s
        while True:
            event.clear()
            if after_epoch is not None and self._space_epoch != after_epoch:
                return True
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return after_epoch is not None and self._space_epoch != after_epoch
            try:
                await asyncio.wait_for(event.wait(), timeout=remaining)
            except asyncio.TimeoutError:
                return after_epoch is not None and self._space_epoch != after_epoch
            if after_epoch is None:
                return True
            if self._space_epoch != after_epoch:
                return True

    def wait_for_available_space_sync(self, timeout_s: float, *, after_epoch: int | None = None) -> bool:
        timeout_s = max(0.0, timeout_s)
        with self._space_available:
            if after_epoch is not None and self._space_epoch != after_epoch:
                return True
            if timeout_s <= 0:
                return False
            notified = self._space_available.wait(timeout=timeout_s)
            if after_epoch is not None:
                return self._space_epoch != after_epoch
            return bool(notified)


    def _effective_limits_unlocked(self) -> tuple[int, int]:
        if self.strategy == "fuzzy":
            return max(0, self._fuzzy_total_limit), max(0, self._fuzzy_per_session_limit)
        return self.total_limit, self.per_session_limit

    def _update_fuzzy_limits_locked(self) -> None:
        if self.strategy != "fuzzy":
            return

        now = monotonic()
        if now - self._last_fuzzy_update < 0.05:
            return
        self._last_fuzzy_update = now

        baseline_total = max(1, self.total_limit)
        baseline_per_session = max(1, self.per_session_limit)
        pressure = min(1.0, self._total_pending_unlocked() / baseline_total)
        attempted_recent = self._attempted_recent
        dropped_recent = self._dropped_recent
        drop_ratio = dropped_recent / max(1, attempted_recent)
        self._maybe_reset_fuzzy_window_locked(now)
        tuned_per, tuned_total = tune_backpressure_limits(
            baseline_per_session,
            baseline_total,
            pressure,
            drop_ratio,
        )

        next_per = max(1, tuned_per)
        next_total = max(next_per, tuned_total)

        if self._fuzzy_per_session_limit > 0:
            per_delta = abs(next_per - self._fuzzy_per_session_limit) / self._fuzzy_per_session_limit
            if per_delta < 0.05:
                next_per = self._fuzzy_per_session_limit

        if self._fuzzy_total_limit > 0:
            total_delta = abs(next_total - self._fuzzy_total_limit) / self._fuzzy_total_limit
            if total_delta < 0.05:
                next_total = self._fuzzy_total_limit

        self._fuzzy_per_session_limit = next_per
        self._fuzzy_total_limit = next_total


    def _maybe_reset_fuzzy_window_locked(self, now: float) -> None:
        if now - self._last_fuzzy_window_reset < 0.25:
            return
        self._attempted_recent = 0
        self._dropped_recent = 0
        self._last_fuzzy_window_reset = now

    def _record_admission_attempt_locked(self, success: bool) -> None:
        if self.strategy != "fuzzy":
            return
        self._attempted_recent += 1
        if not success:
            self._dropped_recent += 1

    def _cleanup_sid_locked(self, sid: int) -> None:
        pending = self._strong_pending.pop(sid, 0)
        self._strong_sessions.pop(sid, None)
        self._refresh_total_pending_locked()
        if pending > 0:
            self._notify_available_space_locked()

    def _collect_session_notifiers_locked(self) -> list[Callable[[], None]]:
        notifiers: list[Callable[[], None]] = []
        sessions: list[object] = []
        try:
            sessions.extend(tuple(self._session_pending.keys()))
        except RuntimeError:
            pass
        sessions.extend(self._strong_sessions.values())
        for session in sessions:
            callback = getattr(session, "_notify_global_space_available", None)
            if callable(callback):
                notifiers.append(callback)
        return notifiers

    def _emit_session_notifiers(self, notifiers: list[Callable[[], None]]) -> None:
        for notify in notifiers:
            try:
                notify()
            except Exception:
                continue

    def _refresh_total_pending_locked(self) -> None:
        self._total_pending = self._total_pending_unlocked()

    def _is_registered_locked(self, session: SessionT) -> bool:
        try:
            return session in self._session_pending
        except TypeError:
            return id(session) in self._strong_pending

    def _session_pending_locked(self, session: SessionT) -> int | None:
        try:
            if session in self._session_pending:
                return self._session_pending[session]
        except TypeError:
            pass
        return self._strong_pending.get(id(session))

    def _set_session_pending_locked(self, session: SessionT, value: int) -> bool:
        try:
            if session in self._session_pending:
                self._session_pending[session] = value
                return True
        except TypeError:
            pass
        sid = id(session)
        if sid in self._strong_pending:
            self._strong_pending[sid] = value
            return True
        return False

    def _register_session_locked(self, session: SessionT) -> None:
        try:
            if session not in self._session_pending:
                self._session_pending[session] = 0
            return
        except TypeError:
            sid = id(session)
            self._strong_sessions[sid] = session
            self._strong_pending.setdefault(sid, 0)

    def _cleanup_stale_locked(self) -> None:
        # WeakKeyDictionary cleanup is automatic for weakrefable sessions.
        # Non-weakrefable sessions are explicit-lifecycle only.
        self._refresh_total_pending_locked()

    def register_session(self, session: SessionT) -> None:
        with self._lock:
            self._cleanup_stale_locked()
            self._register_session_locked(session)
            self._refresh_total_pending_locked()

    def unregister_session(self, session: SessionT) -> None:
        notifiers: list[Callable[[], None]] = []
        with self._lock:
            pending = 0
            removed = False
            try:
                if session in self._session_pending:
                    pending = self._session_pending.pop(session, 0)
                    removed = True
            except TypeError:
                pass
            if not removed:
                sid = id(session)
                pending = self._strong_pending.pop(sid, 0)
                self._strong_sessions.pop(sid, None)
            self._refresh_total_pending_locked()
            if pending > 0:
                self._notify_available_space_locked()
                notifiers = self._collect_session_notifiers_locked()
        self._emit_session_notifiers(notifiers)

    @contextmanager
    def managed_session(self, session: SessionT) -> Iterator[SessionT]:
        self.register_session(session)
        try:
            yield session
        finally:
            self.unregister_session(session)

    def _can_enqueue_unlocked(self, session: SessionT) -> bool:
        current = self._session_pending_locked(session)
        if current is None:
            return False
        self._update_fuzzy_limits_locked()
        total_limit, per_session_limit = self._effective_limits_unlocked()
        total_pending = self._total_pending_unlocked()
        if total_pending >= total_limit:
            return False

        if self.strategy == "proportional":
            active_sessions = max(1, len(self._session_pending) + len(self._strong_pending))
            proportional_limit = max(1, total_limit // active_sessions)
            effective_limit = min(per_session_limit, proportional_limit)
        else:
            effective_limit = per_session_limit
        return current < effective_limit

    def can_enqueue(self, session: SessionT) -> bool:
        with self._lock:
            return self._can_enqueue_unlocked(session)

    def try_enqueue(self, session: SessionT) -> bool:
        with self._lock:
            if not self._is_registered_locked(session):
                self._register_session_locked(session)
            if not self._can_enqueue_unlocked(session):
                self._record_admission_attempt_locked(False)
                return False
            current = self._session_pending_locked(session) or 0
            self._set_session_pending_locked(session, current + 1)
            self._refresh_total_pending_locked()
            self._record_admission_attempt_locked(True)
            return True

    def on_enqueue(self, session: SessionT) -> bool:
        return self.try_enqueue(session)

    def on_dequeue(self, session: SessionT) -> None:
        notifiers: list[Callable[[], None]] = []
        with self._lock:
            current = self._session_pending_locked(session)
            if current is None:
                return
            if current > 0:
                self._set_session_pending_locked(session, current - 1)
                self._refresh_total_pending_locked()
                self._notify_available_space_locked()
                notifiers = self._collect_session_notifiers_locked()
        self._emit_session_notifiers(notifiers)

    def on_reset(self, session: SessionT) -> None:
        notifiers: list[Callable[[], None]] = []
        with self._lock:
            if not self._is_registered_locked(session):
                self._register_session_locked(session)
            prev = self._session_pending_locked(session) or 0
            self._set_session_pending_locked(session, 0)
            self._refresh_total_pending_locked()
            if prev > 0:
                self._notify_available_space_locked()
                notifiers = self._collect_session_notifiers_locked()
        self._emit_session_notifiers(notifiers)
