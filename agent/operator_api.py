"""Thin operator API surface for agent snapshot/replay/control workflows."""

from __future__ import annotations

from typing import Any, Dict

from .decision_pipeline import DecisionPipeline


class AgentOperatorAPI:
    """Minimal endpoint-like wrapper over DecisionPipeline operator methods."""

    def __init__(self, pipeline: DecisionPipeline):
        self.pipeline = pipeline

    def get_agent_snapshot(self) -> Dict[str, Any]:
        """Equivalent to GET /agent/snapshot."""
        return self.pipeline.get_visualization_snapshot()

    def get_agent_replay(self, limit: int = 20) -> Dict[str, Any]:
        """Equivalent to GET /agent/replay."""
        safe_limit = max(1, min(500, int(limit)))
        return {"replay": self.pipeline.get_session_replay(limit=safe_limit), "limit": safe_limit}

    def post_agent_controls(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Equivalent to POST /agent/controls."""
        low_confidence_threshold = payload.get("low_confidence_threshold")
        fallback_action = payload.get("fallback_action")
        tool_failure_fallback_action = payload.get("tool_failure_fallback_action")

        self.pipeline.update_controls(
            low_confidence_threshold=low_confidence_threshold,
            fallback_action=fallback_action,
            tool_failure_fallback_action=tool_failure_fallback_action,
        )
        return {"status": "ok", "controls": self.pipeline.get_visualization_snapshot().get("controls", {})}
