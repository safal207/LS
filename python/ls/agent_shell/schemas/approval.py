from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .task import utc_now

ApprovalActionType = Literal[
    "write_file",
    "git_commit",
    "open_pr",
    "send_email",
    "browser_submit",
    "external_tool",
]
ApprovalStatus = Literal["pending", "approved", "rejected"]


@dataclass(slots=True)
class ApprovalRequest:
    id: str
    task_id: str
    step_id: str
    action_type: ApprovalActionType
    reason: str
    payload_preview: str
    status: ApprovalStatus = "pending"
    created_at: str = field(default_factory=utc_now)
