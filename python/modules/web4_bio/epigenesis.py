from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class EpigenesisPrinciples:
    description: str = "Behavioral adaptation of the network"
    signals: List[str] = ("trust_transition", "routing_feedback", "observability")
