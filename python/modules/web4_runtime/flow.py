from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Generic, TypeVar
from weakref import WeakValueDictionary

MessageT = TypeVar("MessageT")


class BackpressureStrategy(Enum):
    PROPORTIONAL = "proportional"
    FAIR = "fair"
    PRIORITY = "priority"


@dataclass
class GlobalFlowController(Generic[MessageT]):
    max_total_pending: int
    per_session_limit: int
    strategy: BackpressureStrategy = BackpressureStrategy.PROPORTIONAL
    _total_pending: int = field(default=0, init=False)
    _session_pending: dict[int, int] = field(default_factory=dict, init=False)
    _sessions: WeakValueDictionary[int, object] = field(default_factory=WeakValueDictionary, init=False)
    _rr_index: int = field(default=0, init=False)
    _lock: Lock = field(default_factory=Lock, init=False)

    def register_session(self, session: object) -> None:
        key = id(session)
        with self._lock:
            self._sessions[key] = session
            self._session_pending.setdefault(key, 0)

    def set_strategy(self, strategy: BackpressureStrategy) -> None:
        with self._lock:
            self.strategy = strategy

    def can_enqueue(self, session: object) -> bool:
        key = id(session)
        with self._lock:
            self._cleanup_stale_locked()
            if self._total_pending >= self.max_total_pending:
                return False
            if self._session_pending.get(key, 0) >= self.per_session_limit:
                return False
            return self._check_strategy_locked(key)

    def _check_strategy_locked(self, key: int) -> bool:
        if self.strategy == BackpressureStrategy.PROPORTIONAL:
            active = max(1, len(self._sessions))
            proportional_limit = max(1, self.max_total_pending // active)
            return self._session_pending.get(key, 0) <= max(self.per_session_limit, proportional_limit)
        if self.strategy == BackpressureStrategy.FAIR:
            keys = list(self._sessions.keys())
            if not keys:
                return True
            current = keys[self._rr_index % len(keys)]
            return current == key
        if self.strategy == BackpressureStrategy.PRIORITY:
            # Session-priority orchestration can be added later; keep permissive fallback.
            return True
        return True

    def on_enqueue(self, session: object) -> None:
        key = id(session)
        with self._lock:
            self._cleanup_stale_locked()
            self._total_pending += 1
            self._session_pending[key] = self._session_pending.get(key, 0) + 1
            if self.strategy == BackpressureStrategy.FAIR and self._sessions:
                self._rr_index = (self._rr_index + 1) % len(self._sessions)

    def on_dequeue(self, session: object) -> None:
        key = id(session)
        with self._lock:
            self._session_pending[key] = max(0, self._session_pending.get(key, 0) - 1)
            self._total_pending = max(0, self._total_pending - 1)

    def _cleanup_stale_locked(self) -> None:
        stale_keys = [key for key in self._session_pending if key not in self._sessions]
        for key in stale_keys:
            self._total_pending = max(0, self._total_pending - self._session_pending.get(key, 0))
            self._session_pending.pop(key, None)
