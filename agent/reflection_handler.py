"""Action handler for reflection proposals."""

from __future__ import annotations

from typing import Any, Dict

from .decision_pipeline import DecisionPipeline


class ReflectionActionHandler:
    def __init__(self, pipeline: DecisionPipeline):
        self.pipeline = pipeline

    def apply(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        if proposal.get("disable_tool") and proposal.get("change_type") == "tool_demotion":
            return {"status": "blocked", "reason": "tool_disabled", "proposal_id": proposal.get("proposal_id")}

        change_type = proposal.get("change_type")
        if change_type == "control_update":
            self.pipeline.update_controls(**{proposal.get("target"): proposal.get("proposed_value")})
        elif change_type == "tool_demotion":
            target = proposal.get("target")
            if target in self.pipeline.allowed_tool_actions:
                self.pipeline.allowed_tool_actions.discard(target)
        return {"status": "applied", "proposal_id": proposal.get("proposal_id")}

    def reject(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "rejected", "proposal_id": proposal.get("proposal_id")}
