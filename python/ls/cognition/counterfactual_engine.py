from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ls.cognition.state_tracker import AgentState

if TYPE_CHECKING:
    from ls.cognition.motivation_engine import AgentGoal


@dataclass(frozen=True)
class CounterfactualOutcome:
    goal_id: str
    predicted_effect: float
    predicted_cost: float
    category_effects: dict[str, float]


class CounterfactualEngine:
    """What-if simulator with category-aware interaction effects."""

    def evaluate(
        self,
        state: AgentState,
        chosen_goal: AgentGoal,
        alternative_goals: list[AgentGoal],
    ) -> list[CounterfactualOutcome]:
        stress = _clamp01(float(state.context.get("stress", 0.0) or 0.0))
        outcomes: list[CounterfactualOutcome] = []

        for goal in alternative_goals:
            normalized_priority = _clamp01(goal.priority)
            predicted_effect = _clamp01((0.6 * normalized_priority) + (0.4 * (1.0 - stress)))

            category_effects: dict[str, float] = {}
            for need in goal.linked_needs:
                category = need.category.value
                interference = sum(
                    _clamp01(0.2 * other_goal.priority)
                    for other_goal in alternative_goals
                    if other_goal.id != goal.id
                    for other_need in other_goal.linked_needs
                    if other_need.category.value == category
                )
                category_effects[category] = _clamp01(predicted_effect - interference)

            overlap_penalty = sum(category_effects.values()) * 0.1
            predicted_cost = _clamp01((1.0 - normalized_priority) + overlap_penalty)
            outcomes.append(
                CounterfactualOutcome(
                    goal_id=goal.id,
                    predicted_effect=predicted_effect,
                    predicted_cost=predicted_cost,
                    category_effects=category_effects,
                )
            )

        return outcomes


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))
