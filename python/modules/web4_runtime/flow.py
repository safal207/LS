from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Condition, RLock
from typing import Generic, Iterator, Literal, TypeVar
from weakref import WeakKeyDictionary

SessionT = TypeVar("SessionT")
BackpressureStrategy = Literal["fixed", "proportional"]


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
    _async_space_available: asyncio.Condition | None = field(default=None, init=False)
    _async_loop: asyncio.AbstractEventLoop | None = field(default=None, init=False)
    _space_epoch: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self._space_available = Condition(self._lock)

    @property
    def total_pending(self) -> int:
        with self._lock:
            self._refresh_total_pending_locked()
            return self._total_pending

    @property
    def active_sessions(self) -> int:
        with self._lock:
            return len(self._session_pending) + len(self._strong_pending)

    def _total_pending_unlocked(self) -> int:
        attempts = 0
        while attempts < 3:
            try:
                weak_values = tuple(self._session_pending.values())
                break
            except RuntimeError:
                attempts += 1
        else:
            weak_values = ()
        return sum(weak_values) + sum(self._strong_pending.values())

    def _schedule_async_notify(self) -> None:
        if self._async_space_available is None:
            return
        loop = self._async_loop
        if loop is None or loop.is_closed():
            return
        loop.create_task(self.notify_available_space())

    def _notify_available_space_locked(self) -> None:
        self._space_epoch += 1
        self._space_available.notify_all()
        loop = self._async_loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(self._schedule_async_notify)

    def _ensure_async_condition(self) -> asyncio.Condition:
        loop = asyncio.get_running_loop()
        if self._async_space_available is None:
            self._async_space_available = asyncio.Condition()
            self._async_loop = loop
            return self._async_space_available
        if self._async_loop is None:
            self._async_loop = loop
            return self._async_space_available
        if self._async_loop is not loop:
            raise RuntimeError("GlobalFlowController async waiters must run on a single event loop")
        return self._async_space_available

    async def notify_available_space(self) -> None:
        condition = self._ensure_async_condition()
        async with condition:
            condition.notify_all()

    def current_space_epoch(self) -> int:
        with self._lock:
            return self._space_epoch

    async def wait_for_available_space(self, timeout_s: float, *, after_epoch: int | None = None) -> bool:
        condition = self._ensure_async_condition()
        timeout_s = max(0.0, timeout_s)
        try:
            async with condition:
                if after_epoch is not None:
                    with self._lock:
                        if self._space_epoch != after_epoch:
                            return True
                await asyncio.wait_for(condition.wait(), timeout=timeout_s)
            return True
        except asyncio.TimeoutError:
            if after_epoch is not None:
                with self._lock:
                    return self._space_epoch != after_epoch
            return False

    def _cleanup_sid_locked(self, sid: int) -> None:
        pending = self._strong_pending.pop(sid, 0)
        self._strong_sessions.pop(sid, None)
        self._refresh_total_pending_locked()
        if pending > 0:
            self._notify_available_space_locked()

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
        total_pending = self._total_pending_unlocked()
        if total_pending >= self.total_limit:
            return False

        if self.strategy == "proportional":
            active_sessions = max(1, len(self._session_pending) + len(self._strong_pending))
            proportional_limit = max(1, self.total_limit // active_sessions)
            effective_limit = min(self.per_session_limit, proportional_limit)
        else:
            effective_limit = self.per_session_limit
        return current < effective_limit

    def can_enqueue(self, session: SessionT) -> bool:
        with self._lock:
            return self._can_enqueue_unlocked(session)

    def try_enqueue(self, session: SessionT) -> bool:
        with self._lock:
            if not self._is_registered_locked(session):
                self._register_session_locked(session)
            if not self._can_enqueue_unlocked(session):
                return False
            current = self._session_pending_locked(session) or 0
            self._set_session_pending_locked(session, current + 1)
            self._refresh_total_pending_locked()
            return True

    def on_enqueue(self, session: SessionT) -> None:
        _ = self.try_enqueue(session)

    def on_dequeue(self, session: SessionT) -> None:
        with self._lock:
            current = self._session_pending_locked(session)
            if current is None:
                return
            if current > 0:
                self._set_session_pending_locked(session, current - 1)
                self._refresh_total_pending_locked()
                self._notify_available_space_locked()

    def on_reset(self, session: SessionT) -> None:
        with self._lock:
            if not self._is_registered_locked(session):
                self._register_session_locked(session)
            prev = self._session_pending_locked(session) or 0
            self._set_session_pending_locked(session, 0)
            self._refresh_total_pending_locked()
            if prev > 0:
                self._notify_available_space_locked()
