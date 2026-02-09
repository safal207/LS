from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class AgentRoles:
    roles: Tuple[str, ...] = (
        "connector",
        "trust_carrier",
        "guardian",
        "conflict_mediator",
        "ecosystem_support",
        "mission_support",
    )
