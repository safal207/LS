from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ls.cognition.motivation_engine import AgentGoal, EmotionalState


@dataclass(frozen=True)
class CognitiveVector:
    values: dict[str, float]

    def distance(self, other: "CognitiveVector") -> float:
        dimensions = set(self.values) | set(other.values)
        return sqrt(
            sum((self.values.get(dim, 0.0) - other.values.get(dim, 0.0)) ** 2 for dim in dimensions)
        )


class CognitivePhaseSpace:
    """Maps agent state and goals into a shared cognitive vector space."""

    def current_state_vector(
        self,
        goals: list[AgentGoal],
        emotional_state: EmotionalState,
        focus: float,
    ) -> CognitiveVector:
        category_levels = self._category_levels(goals)
        return CognitiveVector(
            {
                "stress": emotional_state.normalized_stress(),
                "focus": focus,
                "learning": category_levels.get("learning", 0.0),
                "social": category_levels.get("social", 0.0),
                "creative": category_levels.get("creative", 0.0),
                "survival": category_levels.get("survival", 0.0),
            }
        )

    def goal_vector(self, goal: AgentGoal) -> CognitiveVector:
        base = {
            "stress": 0.5,
            "focus": 0.5,
            "learning": 0.0,
            "social": 0.0,
            "creative": 0.0,
            "survival": 0.0,
        }
        if not goal.linked_needs:
            return CognitiveVector(base)

        for need in goal.linked_needs:
            category = need.category.value
            drive = max(need.intensity - need.satisfaction, 0.0)
            if category in base:
                base[category] = max(base[category], drive)

        # category-specific attractor tendencies
        categories = {need.category.value for need in goal.linked_needs}
        if "learning" in categories:
            base["focus"] = max(base["focus"], 0.8)
            base["stress"] = min(base["stress"], 0.3)
        if "creative" in categories:
            base["focus"] = max(base["focus"], 0.7)
            base["stress"] = min(base["stress"], 0.35)
        if "social" in categories:
            base["stress"] = min(base["stress"], 0.45)
        if "survival" in categories:
            base["stress"] = max(base["stress"], 0.6)
            base["focus"] = max(base["focus"], 0.75)

        return CognitiveVector(base)

    def alignment(self, current_state: CognitiveVector, goal: AgentGoal) -> float:
        """Return normalized alignment in [0,1], where 1 means identical vectors."""
        distance = current_state.distance(self.goal_vector(goal))
        return 1.0 / (1.0 + distance)

    @staticmethod
    def _category_levels(goals: list[AgentGoal]) -> dict[str, float]:
        levels = {"learning": 0.0, "social": 0.0, "creative": 0.0, "survival": 0.0}
        if not goals:
            return levels

        for goal in goals:
            for need in goal.linked_needs:
                category = need.category.value
                if category in levels:
                    levels[category] = max(levels[category], max(need.intensity - need.satisfaction, 0.0))
        return levels
