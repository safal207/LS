from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Generic, Literal, TypeVar
import weakref

SessionT = TypeVar("SessionT")
BackpressureStrategy = Literal["fixed", "proportional"]


@dataclass
class GlobalFlowController(Generic[SessionT]):
    total_limit: int = 10_000
    per_session_limit: int = 1_000
    strategy: BackpressureStrategy = "fixed"
    _session_pending: dict[int, int] = field(default_factory=dict, init=False)
    _session_refs: dict[int, weakref.ReferenceType[object]] = field(default_factory=dict, init=False)
    _lock: RLock = field(default_factory=RLock, init=False)

    def _session_key(self, session: SessionT) -> int:
        return id(session)

    def register_session(self, session: SessionT) -> None:
        key = self._session_key(session)
        with self._lock:
            self._session_pending.setdefault(key, 0)
            try:
                self._session_refs[key] = weakref.ref(session, lambda _obj, k=key: self._cleanup_key(k))
            except TypeError:
                # Non-weakrefable objects can still be tracked during process lifetime.
                pass

    def unregister_session(self, session: SessionT) -> None:
        self._cleanup_key(self._session_key(session))

    def _cleanup_key(self, key: int) -> None:
        with self._lock:
            self._session_pending.pop(key, None)
            self._session_refs.pop(key, None)

    def on_enqueue(self, session: SessionT) -> None:
        key = self._session_key(session)
        with self._lock:
            self._session_pending[key] = self._session_pending.get(key, 0) + 1

    def on_dequeue(self, session: SessionT) -> None:
        key = self._session_key(session)
        with self._lock:
            current = self._session_pending.get(key, 0)
            self._session_pending[key] = max(0, current - 1)

    def on_reset(self, session: SessionT) -> None:
        key = self._session_key(session)
        with self._lock:
            self._session_pending[key] = 0

    def can_enqueue(self, session: SessionT) -> bool:
        key = self._session_key(session)
        with self._lock:
            total_pending = sum(self._session_pending.values())
            if total_pending >= self.total_limit:
                return False

            current = self._session_pending.get(key, 0)
            if self.strategy == "proportional":
                active_sessions = max(1, len(self._session_pending))
                proportional_limit = max(1, self.total_limit // active_sessions)
                effective_limit = min(self.per_session_limit, proportional_limit)
            else:
                effective_limit = self.per_session_limit
            return current < effective_limit
