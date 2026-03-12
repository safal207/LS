from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable

import psutil

from modules.shared.bootstrap import RuntimeContext


@dataclass(frozen=True)
class MonitorAlert:
    type: str
    payload: dict[str, Any]


class MonitorService:
    """Centralized runtime metrics with lightweight alert subscriptions."""

    def __init__(
        self,
        ctx: RuntimeContext,
        queue_names: list[str] | None = None,
        resource_cache_ttl_s: float = 1.0,
    ):
        self.ctx = ctx
        self.queue_names = queue_names or ["llm_queue", "ui_queue", "audio_queue"]
        self.resource_cache_ttl_s = resource_cache_ttl_s
        self._alert_handlers: dict[str, list[Callable[[MonitorAlert], None]]] = defaultdict(list)
        self._queue_last_seen: dict[str, tuple[float, int]] = {}
        self._latencies: dict[str, list[float]] = defaultdict(list)
        self._resource_cache: dict[str, Any] | None = None
        self._resource_cache_ts = 0.0
        self.ctx.event_bus.subscribe("plugin_failed", self._on_plugin_failure)
        self.ctx.event_bus.subscribe("plugin_load_failed", self._on_plugin_failure)
        self.ctx.event_bus.subscribe("plugin_shutdown_failed", self._on_plugin_failure)

    def register(self) -> None:
        if not self.ctx.services.has("monitor"):
            self.ctx.services.register("monitor", self)

    def subscribe_alert(self, event_type: str, callback: Callable[[MonitorAlert], None]) -> None:
        self._alert_handlers[event_type].append(callback)

    def record_latency(self, component: str, duration_ms: float) -> None:
        self._latencies[component].append(duration_ms)

    def get_queue_stats(self) -> dict[str, dict[str, float | int | None]]:
        now = time.monotonic()
        stats: dict[str, dict[str, float | int | None]] = {}
        for queue_name in self.queue_names:
            queue_obj = self.ctx.services.get(queue_name) if self.ctx.services.has(queue_name) else None
            if queue_obj is None or not hasattr(queue_obj, "qsize"):
                stats[queue_name] = {"size": None, "capacity": None, "utilization": None, "throughput": 0.0}
                continue

            size = int(queue_obj.qsize())
            maxsize = getattr(queue_obj, "maxsize", 0)
            capacity = int(maxsize) if maxsize and maxsize > 0 else None
            utilization = (size / capacity) if capacity else None

            prev_ts, prev_size = self._queue_last_seen.get(queue_name, (now, size))
            elapsed = max(now - prev_ts, 1e-9)
            throughput = abs(size - prev_size) / elapsed
            self._queue_last_seen[queue_name] = (now, size)

            stats[queue_name] = {
                "size": size,
                "capacity": capacity,
                "utilization": utilization,
                "throughput": throughput,
            }

            if utilization is not None and utilization >= 0.8:
                self._emit_alert(
                    "queue_high_utilization",
                    {
                        "queue": queue_name,
                        "utilization": utilization,
                        "size": size,
                        "capacity": capacity,
                    },
                )

        return stats

    def get_resource_usage(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._resource_cache and (now - self._resource_cache_ts) < self.resource_cache_ttl_s:
            return dict(self._resource_cache)

        virtual_mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        self._resource_cache = {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_percent": virtual_mem.percent,
            "memory_used": virtual_mem.used,
            "memory_total": virtual_mem.total,
            "disk_percent": disk.percent,
            "disk_used": disk.used,
            "disk_total": disk.total,
        }
        self._resource_cache_ts = now
        return dict(self._resource_cache)

    def get_event_bus_stats(self) -> dict[str, Any]:
        return {
            "total_subscribers": self.ctx.event_bus.subscriber_count(),
            "subscribers_by_event": self.ctx.event_bus.subscriber_snapshot(),
        }

    def get_latency_stats(self) -> dict[str, dict[str, float]]:
        out: dict[str, dict[str, float]] = {}
        for component, values in self._latencies.items():
            if not values:
                continue
            out[component] = {
                "count": float(len(values)),
                "avg_ms": sum(values) / len(values),
                "max_ms": max(values),
            }
            if component == "llm" and out[component]["avg_ms"] > 5000:
                self._emit_alert("llm_timeout", {"avg_ms": out[component]["avg_ms"]})
        return out

    def snapshot(self) -> dict[str, Any]:
        return {
            "queues": self.get_queue_stats(),
            "resources": self.get_resource_usage(),
            "event_bus": self.get_event_bus_stats(),
            "latency": self.get_latency_stats(),
        }

    def _emit_alert(self, event_type: str, payload: dict[str, Any]) -> None:
        alert = MonitorAlert(type=event_type, payload=payload)
        for handler in self._alert_handlers.get(event_type, []):
            try:
                handler(alert)
            except Exception:
                continue

    def _on_plugin_failure(self, event: Any) -> None:
        self._emit_alert("plugin_failure", dict(getattr(event, "payload", {}) or {}))
