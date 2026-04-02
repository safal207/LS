from __future__ import annotations

from dataclasses import dataclass
from ls.cognition.strategy_planner import StrategyPlanner
from ls.cognition.motivation_engine import AgentGoal
from ls.cognition.need_market_engine import GoalContract


@dataclass
class MockGoal:
    id: str
    priority: float


def test_fallback_strategy_steps():
    planner = StrategyPlanner()
    goal = MockGoal(id="test-goal", priority=0.5)
    strategy = planner.build_strategy(goal)

    assert strategy.steps == ["assess_goal:test-goal", "execute_goal:test-goal", "verify_outcome:test-goal"]


def test_high_priority_goal_steps():
    planner = StrategyPlanner()
    goal = MockGoal(id="priority-goal", priority=0.9)
    strategy = planner.build_strategy(goal)

    assert "prepare_execution:priority-goal" in strategy.steps
    assert "consolidate_learning:priority-goal" in strategy.steps
    assert strategy.steps == [
        "assess_goal:priority-goal",
        "prepare_execution:priority-goal",
        "execute_goal:priority-goal",
        "verify_outcome:priority-goal",
        "consolidate_learning:priority-goal"
    ]


def test_contract_based_strategy_steps():
    planner = StrategyPlanner()
    goal = MockGoal(id="contract-goal", priority=0.5)
    contract = GoalContract(
        id="c1",
        need_id="n1",
        expected_effect=0.8,
        cost=0.1,
        priority=0.7,
        capability_ids=("cap1", "cap2"),
        strategy_idea_id="idea1"
    )
    strategy = planner.build_strategy(goal, contract)

    assert "assess_need:n1" in strategy.steps
    assert "apply_capability:cap1" in strategy.steps
    assert "apply_capability:cap2" in strategy.steps
    assert "execute_goal:contract-goal" not in strategy.steps


def test_medium_priority_goal_gets_consolidation():
    planner = StrategyPlanner()
    goal = MockGoal(id="med-goal", priority=0.75)
    strategy = planner.build_strategy(goal)

    assert "prepare_execution:med-goal" not in strategy.steps
    assert "consolidate_learning:med-goal" in strategy.steps
