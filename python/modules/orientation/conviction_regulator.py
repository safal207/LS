from __future__ import annotations

from typing import Any

from .metrics import clamp


class ConvictionRegulator:
    """
    Skeleton: computes a confidence budget signal.
    """

    def __init__(self, *, max_age: float = 365.0) -> None:
        self.max_age = max_age

    def evaluate(self, inputs: dict[str, Any] | None) -> float:
        data = inputs or {}
        if "confidence_budget" in data:
            return clamp(float(data["confidence_budget"]))

        support = float(data.get("support_level", 0.0))
        diversity = float(data.get("diversity_of_evidence", 0.0))
        conflict = float(data.get("conflict_level", 0.0))
        belief_age = float(data.get("belief_age", 0.0))

        age_norm = clamp(belief_age / self.max_age)
        budget = (0.4 * support) + (0.3 * diversity) + (0.2 * age_norm) - (0.3 * conflict)
        return clamp(budget)
