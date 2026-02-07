from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

from .ltp import LTPProfile


@dataclass(frozen=True)
class ThreadEvent:
    event_id: str
    state_before: str
    state_after: str
    decision_record_id: str
    memory_record_id: str
    identity_snapshot: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def transition_label(self) -> str:
        return f"{self.state_before}->{self.state_after}"


@dataclass
class LiminalThread:
    thread_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    events: List[ThreadEvent] = field(default_factory=list)

    def add_event(
        self,
        *,
        state_before: str,
        state_after: str,
        decision_record_id: str,
        memory_record_id: str,
        identity_snapshot: Dict[str, Any],
    ) -> ThreadEvent:
        event = ThreadEvent(
            event_id=str(uuid.uuid4()),
            state_before=state_before,
            state_after=state_after,
            decision_record_id=decision_record_id,
            memory_record_id=memory_record_id,
            identity_snapshot=dict(identity_snapshot),
        )
        self.events.append(event)
        return event


@dataclass
class CognitiveThread(LiminalThread):
    priority: float = 1.0
    attention_weight: float = 1.0
    active: bool = True
    tags: List[str] = field(default_factory=list)
    cpu_affinity: List[int] = field(default_factory=list)
    numa_node: int | None = None
    ltp: LTPProfile = field(default_factory=LTPProfile)
    last_active_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def touch(self, timestamp: str | None = None) -> None:
        self.last_active_timestamp = timestamp or datetime.now(timezone.utc).isoformat()


class ThreadFactory:
    def __init__(self) -> None:
        self._threads: Dict[str, CognitiveThread] = {}

    def get_thread(self, thread_id: str | None = None) -> CognitiveThread:
        if thread_id and thread_id in self._threads:
            return self._threads[thread_id]
        thread = CognitiveThread(thread_id=thread_id or str(uuid.uuid4()))
        self._threads[thread.thread_id] = thread
        return thread

    def list_threads(self) -> List[CognitiveThread]:
        return list(self._threads.values())
