from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass(frozen=True)
class ObservabilityEvent:
    event_type: str
    payload: Dict[str, Any]
    occurred_at: str


class ObservabilityHub:
    def __init__(self) -> None:
        self._events: List[ObservabilityEvent] = []

    def record(self, event_type: str, payload: Dict[str, Any]) -> ObservabilityEvent:
        event = ObservabilityEvent(
            event_type=event_type,
            payload=payload,
            occurred_at=datetime.now(timezone.utc).isoformat(),
        )
        self._events.append(event)
        return event

    def snapshot(self) -> List[ObservabilityEvent]:
        return list(self._events)
