from __future__ import annotations

import copy
from typing import Any


def _coerce_timestamp(event: dict[str, Any]) -> float:
    ts = event.get("timestamp")
    if isinstance(ts, (int, float)):
        return float(ts)
    return 0.0


def _iter_cognitive_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered = [event for event in events if event.get("type") == "cognitive_state"]
    return sorted(filtered, key=_coerce_timestamp)


def reconstruct_cognitive_state_from_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Reconstruct latest cognitive state using observability events.

    Expected input: observability events emitted by AgentLoop.event_sink.
    Uses `cognitive_state` events and reads payload.state when present.
    """

    timeline: list[dict[str, Any]] = []
    latest_state: dict[str, Any] = {}
    latest_snapshot_id: str | None = None

    for event in _iter_cognitive_events(events):
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        state = payload.get("state")
        if isinstance(state, dict):
            latest_state = copy.deepcopy(state)

        snapshot_id = payload.get("snapshot_id")
        if isinstance(snapshot_id, str) and snapshot_id:
            latest_snapshot_id = snapshot_id

        timeline.append(
            {
                "timestamp": event.get("timestamp"),
                "task_id": event.get("task_id"),
                "snapshot_id": snapshot_id,
                "diff": payload.get("diff") or {},
            }
        )

    return {
        "snapshot_id": latest_snapshot_id,
        "state": latest_state,
        "timeline": timeline,
    }


def reconstruct_cognitive_state_at_timestamp(events: list[dict[str, Any]], at_timestamp: float) -> dict[str, Any]:
    """Reconstruct state at or before provided timestamp."""
    filtered = [event for event in events if _coerce_timestamp(event) <= at_timestamp]
    return reconstruct_cognitive_state_from_events(filtered)
