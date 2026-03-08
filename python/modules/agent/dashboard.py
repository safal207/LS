from __future__ import annotations

import json
from statistics import mean
from typing import Any

from .reconstruction import reconstruct_cognitive_state_from_events


_TIMELINE_KEYS = ("beliefs", "causal_edges", "temporal_nodes")


def _extract_weight(belief: Any) -> float:
    if not isinstance(belief, dict):
        return 1.0
    for key in ("weight", "resonance", "score"):
        value = belief.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return 1.0


def _safe_metric(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _build_timeline(cognitive_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    for event in cognitive_events:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        event_state = payload.get("state") if isinstance(payload.get("state"), dict) else {}
        mission = event_state.get("mission_state") if isinstance(event_state.get("mission_state"), dict) else {}
        point: dict[str, Any] = {
            "timestamp": event.get("timestamp"),
            "snapshot_id": payload.get("snapshot_id"),
            "beliefs": len(event_state.get("beliefs") or []),
            "causal_edges": len(event_state.get("causal_edges") or []),
            "temporal_nodes": len(event_state.get("temporal_nodes") or []),
            "confidence": _safe_metric(mission.get("confidence")),
            "adaptive_bias": _safe_metric(mission.get("adaptive_bias")),
            "trajectory_error": _safe_metric(mission.get("trajectory_error")),
        }
        if previous is not None:
            point["delta"] = {
                key: int(point[key]) - int(previous.get(key, 0))
                for key in _TIMELINE_KEYS
            }
        timeline.append(point)
        previous = point
    return timeline


def build_cognitive_dashboard(events: list[dict[str, Any]], *, last_n: int = 20) -> dict[str, Any]:
    """Build read-only dashboard payload from observability events."""

    cognitive_events = [event for event in events if event.get("type") == "cognitive_state"]
    if last_n > 0:
        cognitive_events = cognitive_events[-last_n:]

    reconstructed = reconstruct_cognitive_state_from_events(cognitive_events)
    state = reconstructed.get("state") if isinstance(reconstructed.get("state"), dict) else {}
    beliefs = state.get("beliefs") if isinstance(state.get("beliefs"), list) else []
    weights = [_extract_weight(belief) for belief in beliefs]
    timeline = _build_timeline(cognitive_events)

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
    timeline = dashboard.get("timeline") if isinstance(dashboard.get("timeline"), list) else []
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
    if timeline and isinstance(timeline[-1], dict) and isinstance(timeline[-1].get("delta"), dict):
        delta = timeline[-1]["delta"]
        lines.append(
            "last_delta: "
            + ", ".join(f"{key}={value:+d}" for key, value in sorted(delta.items()))
        )
    return "\n".join(lines)
