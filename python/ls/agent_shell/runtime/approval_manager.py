from __future__ import annotations

from dataclasses import asdict
from uuid import uuid4

from ls.agent_shell.schemas.approval import ApprovalRequest
from ls.agent_shell.schemas.step import Step
from ls.agent_shell.storage.sqlite_store import SQLiteStore


class ApprovalManager:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def requires_approval(self, step: Step, mode: str) -> bool:
        risky_types = {"write", "git", "browser", "tool"}
        if mode == "read-only":
            return False
        return step.type in risky_types

    def request(self, task_id: str, step: Step) -> ApprovalRequest:
        action_map = {
            "write": "write_file",
            "git": "git_commit",
            "browser": "browser_submit",
            "tool": "external_tool",
        }
        approval = ApprovalRequest(
            id=f"approval-{uuid4().hex[:8]}",
            task_id=task_id,
            step_id=step.id,
            action_type=action_map.get(step.type, "write_file"),  # type: ignore[arg-type]
            reason=f"Step '{step.title}' may mutate state or trigger external side effects.",
            payload_preview=f"type={step.type}; title={step.title}; description={step.description}",
        )
        self.store.insert("approvals", asdict(approval))
        return approval

    def set_status(self, approval_id: str, status: str) -> None:
        self.store.update("approvals", "id", approval_id, status=status)
