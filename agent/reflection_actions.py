"""Dashboard actions for applying reflection proposals to a decision pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .cognition import CognitiveTransaction
from .decision_pipeline import DecisionPipeline


class ReflectionActionHandler:
    """Apply or reject reflection proposals and persist a structured action log."""

    def __init__(self, pipeline: DecisionPipeline):
        self.pipeline = pipeline

    def auto_apply_high_confidence(self, proposals: Iterable[Dict[str, Any]]) -> List[str]:
        """Automatically apply proposals with confidence >= 0.9."""
        high_confidence = [item for item in proposals if float(item.get("confidence", 0.0)) >= 0.9]
        if not high_confidence:
            return []
        messages = self.apply_selected(high_confidence, action="auto_apply")
        return messages

    def apply_selected(self, proposals: Iterable[Dict[str, Any]], action: str = "approve") -> List[str]:
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
                self.pipeline.append_cognitive_transaction(
                    CognitiveTransaction.create(
                        actor="human",
                        action="approve_proposal",
                        payload={"proposal_id": proposal.get("proposal_id"), "data": proposal},
                    )
                )
                self.pipeline.register_action_activity(
                    "control_update",
                    {"target": target, "proposed_value": proposed_value},
                )

            elif change_type == "tool_demotion":
                disabled = self.pipeline.tool_runtime.disable_tool(target)
                messages.append(f"approved tool_demotion: {target} disabled={disabled}")
                self.pipeline.append_cognitive_transaction(
                    CognitiveTransaction.create(
                        actor="human",
                        action="approve_proposal",
                        payload={"proposal_id": proposal.get("proposal_id"), "data": proposal},
                    )
                )
                self.pipeline.register_action_activity(
                    "tool_demotion",
                    {"target": target, "disabled": disabled},
                )
            else:
                messages.append(f"skipped unknown proposal type: {change_type}")
                self.pipeline.register_action_activity(
                    "strategy_mutation",
                    {"change_type": change_type, "target": target, "proposed_value": proposed_value},
                )

        self._append_log(action, messages)
        self.pipeline.save_state(str(Path("reflection_state.json")))
        return messages

    def reject_selected(self, proposals: Iterable[Dict[str, Any]]) -> List[str]:
        """Reject selected proposals and return rejection messages."""
        proposal_list = list(proposals)
        messages = [f"rejected proposal: {item.get('proposal_id')}" for item in proposal_list]
        for item in proposal_list:
            self.pipeline.append_cognitive_transaction(
                CognitiveTransaction.create(
                    actor="human",
                    action="reject_proposal",
                    payload={"proposal_id": item.get("proposal_id")},
                )
            )
            self.pipeline.register_action_activity(
                "strategy_mutation",
                {
                    "proposal_id": item.get("proposal_id"),
                    "status": "rejected",
                    "change_type": item.get("change_type"),
                },
            )
        self._append_log("reject", messages)
        self.pipeline.save_state(str(Path("reflection_state.json")))
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
