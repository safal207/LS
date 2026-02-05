from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class TrajectoryPoint:
    decision: str
    context: dict[str, Any]
    outcome: Optional[dict[str, Any]] = None


class TrajectoryLayer:
    """
    Phase 14.1 - Trajectory Layer

    Tracks sequences of decisions, contexts, and outcomes.
    Skeleton: no learning, only recording and simple deviation metrics.
    """

    def __init__(self, max_history: int = 100) -> None:
        self.max_history = max_history
        self.history: list[TrajectoryPoint] = []

    def record_decision(self, decision: str, context: dict[str, Any]) -> None:
        self.history.append(TrajectoryPoint(decision=decision, context=context))
        if len(self.history) > self.max_history:
            self.history.pop(0)

    def record_outcome(self, outcome: dict[str, Any]) -> None:
        if not self.history:
            return
        self.history[-1].outcome = outcome

    def compute_trajectory_error(self) -> float:
        """
        Skeleton: mismatch rate between expected and actual outcomes.
        Uses outcome['success'] == False as an error signal.
        """
        errors = 0
        total = 0
        for point in self.history:
            if point.outcome is None:
                continue
            total += 1
            if point.outcome.get("success") is False:
                errors += 1
        return errors / total if total else 0.0
