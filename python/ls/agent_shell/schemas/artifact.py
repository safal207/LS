from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .task import utc_now

ArtifactType = Literal["file", "diff", "doc", "pr", "screenshot", "report"]


@dataclass(slots=True)
class Artifact:
    id: str
    task_id: str
    type: ArtifactType
    title: str
    path_or_url: str
    metadata: dict = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
