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

    def federation_metrics(self) -> Dict[str, Any]:
        total = 0
        allowed = 0
        denied = 0
        by_policy: Dict[str, int] = {}
        denied_by_reason: Dict[str, int] = {}

        for event in self._events:
            payload = event.payload
            raw_allowed = payload.get("federation_allowed")
            if not isinstance(raw_allowed, bool):
                continue

            total += 1
            if raw_allowed:
                allowed += 1
            else:
                denied += 1

            policy = str(payload.get("federation_policy", "unknown"))
            by_policy[policy] = by_policy.get(policy, 0) + 1

            if not raw_allowed:
                reason = str(payload.get("federation_reason", "unknown"))
                denied_by_reason[reason] = denied_by_reason.get(reason, 0) + 1

        return {
            "total": total,
            "allowed": allowed,
            "denied": denied,
            "allow_ratio": (allowed / total) if total else 0.0,
            "by_policy": dict(sorted(by_policy.items())),
            "denied_by_reason": dict(sorted(denied_by_reason.items())),
        }
