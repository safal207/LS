from __future__ import annotations

from typing import Any


def reconstruct_cognitive_state_from_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Reconstruct latest cognitive state using observability events.

    Expected input: observability events emitted by AgentLoop.event_sink.
    Uses `cognitive_state` events and reads payload.state when present.
    """

    timeline: list[dict[str, Any]] = []
    latest_state: dict[str, Any] = {}
    latest_snapshot_id: str | None = None

    for event in events:
        if event.get("type") != "cognitive_state":
            continue

        payload = event.get("payload") or {}
        state = payload.get("state")
        if isinstance(state, dict):
            latest_state = dict(state)

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
