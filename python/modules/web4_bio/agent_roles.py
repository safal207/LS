from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class AgentRoles:
    roles: List[str] = (
        "connector",
        "trust_carrier",
        "guardian",
        "conflict_mediator",
        "ecosystem_support",
        "mission_support",
    )
