from __future__ import annotations

import time
from typing import Any, Dict, Optional, TypedDict, Literal

ObservabilityEventType = Literal[
    "input",
    "output",
    "cancel",
    "state_change",
    "phase_transition",
    "metrics",
]

ALLOWED_EVENTS: set[ObservabilityEventType] = {
    "input",
    "output",
    "cancel",
    "state_change",
    "phase_transition",
    "metrics",
}

EVENT_VERSION = "1.0"


class ObservabilityEvent(TypedDict):
    type: ObservabilityEventType
    timestamp: float
    task_id: str
    version: str
    state: Optional[str]
    payload: Dict[str, Any]


def _map_event_type(event_type: str) -> Optional[ObservabilityEventType]:
    mapping: dict[str, ObservabilityEventType] = {
        "input_received": "input",
        "output_ready": "output",
        "cancelled": "cancel",
        "state_change": "state_change",
        "phase_transition": "phase_transition",
        "metrics": "metrics",
    }
    return mapping.get(event_type)


def build_observability_event(
    event_type: str,
    payload: Dict[str, Any] | None,
    state: Optional[str],
    task_id: str | None,
    *,
    timestamp: float | None = None,
) -> ObservabilityEvent | None:
    mapped = _map_event_type(event_type)
    if mapped is None or mapped not in ALLOWED_EVENTS:
        return None
    return {
        "type": mapped,
        "timestamp": time.time() if timestamp is None else timestamp,
        "task_id": task_id or "unknown",
        "version": EVENT_VERSION,
        "state": state,
        "payload": payload or {},
    }
