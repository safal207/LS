from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

TaskMode = Literal["read-only", "safe-write", "full-agent"]
TaskStatus = Literal[
    "queued",
    "planning",
    "running",
    "waiting_approval",
    "blocked",
    "completed",
    "failed",
    "cancelled",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class Task:
    id: str
    title: str
    prompt: str
    mode: TaskMode
    status: TaskStatus
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    summary: str | None = None
