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


class CounterfactualEngine:
    """Lightweight what-if simulator for alternative goals."""

    def evaluate(
        self,
        state: AgentState,
        chosen_goal: AgentGoal,
        alternative_goals: list[AgentGoal],
    ) -> list[CounterfactualOutcome]:
        stress = float(state.context.get("stress", 0.0) or 0.0)
        stress = _clamp01(stress)

        outcomes: list[CounterfactualOutcome] = []
        for goal in alternative_goals:
            normalized_priority = _clamp01(goal.priority)
            predicted_effect = _clamp01((0.65 * normalized_priority) + (0.35 * (1.0 - stress)))
            predicted_cost = _clamp01(1.0 - normalized_priority)
            outcomes.append(
                CounterfactualOutcome(
                    goal_id=goal.id,
                    predicted_effect=predicted_effect,
                    predicted_cost=predicted_cost,
                )
            )

        return outcomes


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))
