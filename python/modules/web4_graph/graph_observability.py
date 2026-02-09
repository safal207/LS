from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass(frozen=True)
class GraphObservabilityEvent:
    event_type: str
    node: str
    peer: str
    payload: Dict[str, Any]
    occurred_at: str


class GraphObservabilityHub:
    def __init__(self) -> None:
        self._events: List[GraphObservabilityEvent] = []

    def record(self, event_type: str, node: str, peer: str, payload: Dict[str, Any]) -> GraphObservabilityEvent:
        event = GraphObservabilityEvent(
            event_type=event_type,
            node=node,
            peer=peer,
            payload=payload,
            occurred_at=datetime.now(timezone.utc).isoformat(),
        )
        self._events.append(event)
        return event

    def snapshot(self) -> List[GraphObservabilityEvent]:
        return list(self._events)
