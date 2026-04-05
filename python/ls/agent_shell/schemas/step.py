from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .task import utc_now

StepType = Literal["read", "analyze", "write", "git", "tool", "browser", "artifact"]
StepStatus = Literal[
    "pending",
    "running",
    "waiting_approval",
    "completed",
    "failed",
    "skipped",
]


@dataclass(slots=True)
class Step:
    id: str
    task_id: str
    title: str
    description: str
    type: StepType
    reason: str
    status: StepStatus = "pending"
    needs_approval: bool = False
    inputs: dict = field(default_factory=dict)
    outputs: dict = field(default_factory=dict)
    started_at: str | None = None
    ended_at: str | None = None

    def mark_running(self) -> None:
        self.status = "running"
        self.started_at = utc_now()

    def mark_done(self) -> None:
        self.status = "completed"
        self.ended_at = utc_now()
