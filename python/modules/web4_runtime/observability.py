from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
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
        return self._federation_metrics_for_events(self._events)

    def federation_metrics_window(self, window_size: int) -> Dict[str, Any]:
        if window_size <= 0:
            return self._federation_metrics_for_events([])
        return self._federation_metrics_for_events(self._events[-window_size:])

    def export_federation_metrics(self, *, window_size: int | None = None) -> Dict[str, Any]:
        if window_size is None:
            metrics = self.federation_metrics()
        else:
            metrics = self.federation_metrics_window(window_size)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "window_size": window_size,
            "metrics": metrics,
        }

    def export_federation_metrics_json(self, *, window_size: int | None = None, pretty: bool = False) -> str:
        payload = self.export_federation_metrics(window_size=window_size)
        if pretty:
            return json.dumps(payload, sort_keys=True, indent=2)
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def export_federation_metrics_prometheus(
        self, *, window_size: int | None = None, namespace: str = "web4_federation"
    ) -> str:
        metrics = (
            self.federation_metrics() if window_size is None else self.federation_metrics_window(window_size)
        )
        prefix = namespace.strip() or "web4_federation"
        lines = [
            f"# HELP {prefix}_total Total federation routing decisions in snapshot.",
            f"# TYPE {prefix}_total gauge",
            f"{prefix}_total {metrics['total']}",
            f"# HELP {prefix}_allowed Allowed federation decisions in snapshot.",
            f"# TYPE {prefix}_allowed gauge",
            f"{prefix}_allowed {metrics['allowed']}",
            f"# HELP {prefix}_denied Denied federation decisions in snapshot.",
            f"# TYPE {prefix}_denied gauge",
            f"{prefix}_denied {metrics['denied']}",
            f"# HELP {prefix}_allow_ratio Allowed decisions ratio in snapshot.",
            f"# TYPE {prefix}_allow_ratio gauge",
            f"{prefix}_allow_ratio {metrics['allow_ratio']}",
            f"# HELP {prefix}_by_policy Federation decisions grouped by policy.",
            f"# TYPE {prefix}_by_policy gauge",
        ]

        by_policy = metrics.get("by_policy", {})
        for policy, count in by_policy.items():
            escaped_policy = self._escape_prometheus_label(str(policy))
            lines.append(f'{prefix}_by_policy{{policy="{escaped_policy}"}} {count}')

        lines.extend(
            [
                f"# HELP {prefix}_denied_by_reason Denied federation decisions grouped by reason.",
                f"# TYPE {prefix}_denied_by_reason gauge",
            ]
        )
        denied_by_reason = metrics.get("denied_by_reason", {})
        for reason, count in denied_by_reason.items():
            escaped_reason = self._escape_prometheus_label(str(reason))
            lines.append(f'{prefix}_denied_by_reason{{reason="{escaped_reason}"}} {count}')

        if window_size is not None:
            lines.extend(
                [
                    f"# HELP {prefix}_window_size Federation metrics rolling window size.",
                    f"# TYPE {prefix}_window_size gauge",
                    f"{prefix}_window_size {window_size}",
                ]
            )

        return "\n".join(lines) + "\n"

    def _federation_metrics_for_events(self, events: List[ObservabilityEvent]) -> Dict[str, Any]:
        total = 0
        allowed = 0
        denied = 0
        by_policy: Dict[str, int] = {}
        denied_by_reason: Dict[str, int] = {}

        for event in events:
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

    @staticmethod
    def _escape_prometheus_label(value: str) -> str:
        return value.replace("\\", r"\\").replace('"', r"\"").replace("\n", r"\n")
