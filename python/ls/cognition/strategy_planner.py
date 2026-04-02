from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ls.cognition.motivation_engine import AgentGoal, Strategy
    from ls.cognition.need_market_engine import GoalContract


class StrategyPlanner:
    """Rich planning policy for building capability-aware strategies."""

    def build_strategy(self, goal: AgentGoal, contract: Optional[GoalContract] = None) -> Strategy:
        from ls.cognition.motivation_engine import Strategy

        steps: list[str] = []

        # 1. Assessment phase
        if contract:
            steps.append(f"assess_need:{contract.need_id}")
        else:
            steps.append(f"assess_goal:{goal.id}")

        # 2. Preparation phase for high-priority goals
        if goal.priority > 0.8:
            steps.append(f"prepare_execution:{goal.id}")

        # 3. Execution phase
        if contract and contract.capability_ids:
            steps.extend(f"apply_capability:{cap_id}" for cap_id in contract.capability_ids)
        else:
            steps.append(f"execute_goal:{goal.id}")

        # 4. Verification phase
        steps.append(f"verify_outcome:{goal.id}")

        # 5. Consolidation phase for significant goals
        if goal.priority > 0.7:
            steps.append(f"consolidate_learning:{goal.id}")

        return Strategy(goal=goal, steps=steps)
