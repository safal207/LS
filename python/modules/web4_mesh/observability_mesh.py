from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass(frozen=True)
class MeshObservabilityEvent:
    event_type: str
    payload: Dict[str, Any]
    occurred_at: str


class MeshObservabilityHub:
    def __init__(self) -> None:
        self._events: List[MeshObservabilityEvent] = []

    def record(self, event_type: str, payload: Dict[str, Any]) -> MeshObservabilityEvent:
        event = MeshObservabilityEvent(
            event_type=event_type,
            payload=payload,
            occurred_at=datetime.now(timezone.utc).isoformat(),
        )
        self._events.append(event)
        return event

    def snapshot(self) -> List[MeshObservabilityEvent]:
        return list(self._events)
