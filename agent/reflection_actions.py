"""Dashboard actions for applying reflection proposals to a decision pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from .decision_pipeline import DecisionPipeline


class ReflectionActionHandler:
    """Apply or reject reflection proposals and persist a structured action log."""

    def __init__(self, pipeline: DecisionPipeline):
        self.pipeline = pipeline

    def apply_selected(self, proposals: Iterable[Dict[str, Any]]) -> List[str]:
        """Apply selected proposals and return human-readable action messages."""
        messages: List[str] = []
        for proposal in proposals:
            change_type = proposal.get("change_type")
            target = str(proposal.get("target"))
            proposed_value = proposal.get("proposed_value")

            if change_type == "control_update":
                if target == "low_confidence_threshold":
                    self.pipeline.update_controls(low_confidence_threshold=float(proposed_value))
                elif target == "fallback_action":
                    self.pipeline.update_controls(fallback_action=str(proposed_value))
                messages.append(f"approved control_update: {target}={proposed_value}")

            elif change_type == "tool_demotion":
                disabled = self.pipeline.tool_runtime.disable_tool(target)
                messages.append(f"approved tool_demotion: {target} disabled={disabled}")
            else:
                messages.append(f"skipped unknown proposal type: {change_type}")

        self._append_log("approve", messages)
        return messages

    def reject_selected(self, proposals: Iterable[Dict[str, Any]]) -> List[str]:
        """Reject selected proposals and return rejection messages."""
        messages = [f"rejected proposal: {item.get('proposal_id')}" for item in proposals]
        self._append_log("reject", messages)
        return messages

    def _append_log(self, action: str, messages: List[str]) -> None:
        """Write a dashboard audit entry into cognitive state."""
        dashboard_log = self.pipeline.cognitive_state.setdefault("reflection_dashboard_log", [])
        dashboard_log.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": action,
                "messages": messages,
            }
        )
