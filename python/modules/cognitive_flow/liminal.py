from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class LiminalState:
    name: str
    from_phase: Optional[str]
    to_phase: Optional[str]
