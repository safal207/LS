from __future__ import annotations

import json
from statistics import mean
from typing import Any

from .reconstruction import reconstruct_cognitive_state_from_events


def _extract_weight(belief: Any) -> float:
    if not isinstance(belief, dict):
        return 1.0
    for key in ("weight", "resonance", "score"):
        value = belief.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return 1.0


def build_cognitive_dashboard(events: list[dict[str, Any]], *, last_n: int = 20) -> dict[str, Any]:
    """Build read-only dashboard payload from observability events.

    The dashboard intentionally consumes only `cognitive_state` events to keep
    replay deterministic and avoid leaking raw user/assistant text payloads.
    """

    cognitive_events = [event for event in events if event.get("type") == "cognitive_state"]
    if last_n > 0:
        cognitive_events = cognitive_events[-last_n:]

    reconstructed = reconstruct_cognitive_state_from_events(cognitive_events)
    state = reconstructed.get("state") if isinstance(reconstructed.get("state"), dict) else {}
    beliefs = state.get("beliefs") if isinstance(state.get("beliefs"), list) else []
    weights = [_extract_weight(belief) for belief in beliefs]

    timeline: list[dict[str, Any]] = []
    for event in cognitive_events:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        event_state = payload.get("state") if isinstance(payload.get("state"), dict) else {}
        mission = event_state.get("mission_state") if isinstance(event_state.get("mission_state"), dict) else {}
        timeline.append(
            {
                "timestamp": event.get("timestamp"),
                "snapshot_id": payload.get("snapshot_id"),
                "beliefs": len(event_state.get("beliefs") or []),
                "causal_edges": len(event_state.get("causal_edges") or []),
                "temporal_nodes": len(event_state.get("temporal_nodes") or []),
                "confidence": float(mission.get("confidence", 0.0)) if isinstance(mission.get("confidence"), (int, float)) else None,
                "adaptive_bias": float(mission.get("adaptive_bias", 0.0)) if isinstance(mission.get("adaptive_bias"), (int, float)) else None,
                "trajectory_error": float(mission.get("trajectory_error", 0.0)) if isinstance(mission.get("trajectory_error"), (int, float)) else None,
            }
        )

    dashboard = {
        "events_analyzed": len(cognitive_events),
        "timeline": timeline,
        "current": {
            "snapshot_id": reconstructed.get("snapshot_id"),
            "beliefs": len(beliefs),
            "causal_edges": len(state.get("causal_edges") or []),
            "temporal_nodes": len(state.get("temporal_nodes") or []),
            "mission_state": dict(state.get("mission_state") or {}),
            "memory_usage_bytes": len(json.dumps(state, ensure_ascii=False).encode("utf-8")),
        },
        "belief_weights": {
            "count": len(weights),
            "avg": mean(weights) if weights else 0.0,
            "min": min(weights) if weights else 0.0,
            "max": max(weights) if weights else 0.0,
        },
    }
    return dashboard


def render_cognitive_dashboard(dashboard: dict[str, Any]) -> str:
    current = dashboard.get("current") if isinstance(dashboard.get("current"), dict) else {}
    mission = current.get("mission_state") if isinstance(current.get("mission_state"), dict) else {}
    lines = [
        "Cognitive Dashboard (read-only)",
        f"events_analyzed: {dashboard.get('events_analyzed', 0)}",
        f"snapshot_id: {current.get('snapshot_id')}",
        f"beliefs: {current.get('beliefs', 0)}",
        f"causal_edges: {current.get('causal_edges', 0)}",
        f"temporal_nodes: {current.get('temporal_nodes', 0)}",
        f"memory_usage_bytes: {current.get('memory_usage_bytes', 0)}",
    ]
    if mission:
        lines.append(f"mission_state_keys: {', '.join(sorted(mission.keys()))}")
    return "\n".join(lines)
