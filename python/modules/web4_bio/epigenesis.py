from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class EpigenesisPrinciples:
    description: str = "Behavioral adaptation of the network"
    signals: Tuple[str, ...] = ("trust_transition", "routing_feedback", "observability")
