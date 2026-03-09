"""Healthcheck scheduler helpers for tool runtime active/passive monitoring."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from .tool_runtime import ToolRuntime


class ToolHealthcheckScheduler:
    """Runs periodic health checks and persists history in cognitive state."""

    def __init__(self, runtime: ToolRuntime, interval_s: float = 30.0):
        self.runtime = runtime
        self.interval_s = interval_s

    def run_once(self, active: bool = True) -> Dict[str, Any]:
        snapshots = self.runtime.run_healthchecks(active=active)
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": "active" if active else "passive",
            "interval_s": self.interval_s,
            "tool_health": snapshots,
        }
        history = self.runtime.cognitive_state.setdefault("tool_healthcheck_history", [])
        if isinstance(history, list):
            history.append(result)
        self.runtime.cognitive_state["last_tool_healthcheck"] = result
        return result
