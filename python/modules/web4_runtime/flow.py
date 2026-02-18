from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Generic, Literal, TypeVar
from weakref import ref

SessionT = TypeVar("SessionT")
BackpressureStrategy = Literal["fixed", "proportional"]


@dataclass
class GlobalFlowController(Generic[SessionT]):
    total_limit: int = 10_000
    per_session_limit: int = 1_000
    strategy: BackpressureStrategy = "fixed"
    _session_pending: dict[int, int] = field(default_factory=dict, init=False)
    _session_refs: dict[int, ref[object]] = field(default_factory=dict, init=False)
    _session_ids_by_objid: dict[int, int] = field(default_factory=dict, init=False)
    _strong_sessions: dict[int, object] = field(default_factory=dict, init=False)
    _next_session_id: int = field(default=1, init=False)
    _total_pending: int = field(default=0, init=False)
    _lock: Lock = field(default_factory=Lock, init=False)

    @property
    def total_pending(self) -> int:
        with self._lock:
            return self._total_pending

    @property
    def active_sessions(self) -> int:
        with self._lock:
            return len(self._session_pending)

    def _cleanup_sid_locked(self, sid: int) -> None:
        pending = self._session_pending.pop(sid, 0)
        self._total_pending = max(0, self._total_pending - pending)
        self._session_refs.pop(sid, None)

    def _cleanup_stale_locked(self) -> None:
        stale_objids: list[int] = []
        for obj_id, sid in self._session_ids_by_objid.items():
            session_ref = self._session_refs.get(sid)
            if session_ref is not None and session_ref() is None:
                stale_objids.append(obj_id)
        for obj_id in stale_objids:
            sid = self._session_ids_by_objid.pop(obj_id, None)
            self._strong_sessions.pop(obj_id, None)
            if sid is not None:
                self._cleanup_sid_locked(sid)

    def _session_sid_locked(self, session: SessionT) -> int:
        obj_id = id(session)
        sid = self._session_ids_by_objid.get(obj_id)
        if sid is not None:
            return sid

        sid = self._next_session_id
        self._next_session_id += 1
        self._session_ids_by_objid[obj_id] = sid
        self._session_pending[sid] = 0
        try:
            self._session_refs[sid] = ref(session)
        except TypeError:
            # Non-weakrefable objects are retained strongly until unregister.
            self._strong_sessions[obj_id] = session
        return sid

    def register_session(self, session: SessionT) -> None:
        with self._lock:
            self._cleanup_stale_locked()
            self._session_sid_locked(session)

    def unregister_session(self, session: SessionT) -> None:
        with self._lock:
            obj_id = id(session)
            sid = self._session_ids_by_objid.pop(obj_id, None)
            self._strong_sessions.pop(obj_id, None)
            if sid is not None:
                self._cleanup_sid_locked(sid)

    def _can_enqueue_unlocked(self, sid: int) -> bool:
        if self._total_pending >= self.total_limit:
            return False

        current = self._session_pending.get(sid, 0)
        if self.strategy == "proportional":
            active_sessions = max(1, len(self._session_pending))
            proportional_limit = max(1, self.total_limit // active_sessions)
            effective_limit = min(self.per_session_limit, proportional_limit)
        else:
            effective_limit = self.per_session_limit
        return current < effective_limit

    def can_enqueue(self, session: SessionT) -> bool:
        with self._lock:
            self._cleanup_stale_locked()
            sid = self._session_sid_locked(session)
            return self._can_enqueue_unlocked(sid)

    def try_enqueue(self, session: SessionT) -> bool:
        with self._lock:
            self._cleanup_stale_locked()
            sid = self._session_sid_locked(session)
            if not self._can_enqueue_unlocked(sid):
                return False
            self._session_pending[sid] = self._session_pending.get(sid, 0) + 1
            self._total_pending += 1
            return True

    def on_enqueue(self, session: SessionT) -> None:
        _ = self.try_enqueue(session)

    def on_dequeue(self, session: SessionT) -> None:
        with self._lock:
            self._cleanup_stale_locked()
            sid = self._session_ids_by_objid.get(id(session))
            if sid is None or sid not in self._session_pending:
                return
            if self._session_pending[sid] > 0:
                self._session_pending[sid] -= 1
                self._total_pending = max(0, self._total_pending - 1)

    def on_reset(self, session: SessionT) -> None:
        with self._lock:
            self._cleanup_stale_locked()
            sid = self._session_ids_by_objid.get(id(session))
            if sid is None:
                sid = self._session_sid_locked(session)
            prev = self._session_pending.get(sid, 0)
            self._session_pending[sid] = 0
            self._total_pending = max(0, self._total_pending - prev)
