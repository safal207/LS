from __future__ import annotations

from typing import Any

from .metrics import clamp, safe_ratio


class BeliefAging:
    """
    Skeleton: computes a stability score from belief ages and support.
    """

    def __init__(self, *, mature_age: float = 30.0, mature_support: float = 0.6, max_age: float = 365.0) -> None:
        self.mature_age = mature_age
        self.mature_support = mature_support
        self.max_age = max_age

    def evaluate(self, beliefs: list[dict[str, Any]] | None) -> float:
        if not beliefs:
            return 0.0

        ages = [float(b.get("age", 0.0)) for b in beliefs]
        supports = [float(b.get("support", 0.0)) for b in beliefs]

        avg_age = safe_ratio(sum(ages), len(ages))
        avg_support = safe_ratio(sum(supports), len(supports))

        mature_count = 0
        for age, support in zip(ages, supports):
            if age >= self.mature_age and support >= self.mature_support:
                mature_count += 1
        mature_ratio = safe_ratio(mature_count, len(ages))

        age_norm = clamp(avg_age / self.max_age)
        score = (0.6 * age_norm) + (0.4 * mature_ratio)
        return clamp(score)
