from __future__ import annotations

from ls.cognition.counterfactual_engine import CounterfactualEngine
from ls.cognition.motivation_engine import AgentGoal, AgentNeed, NeedCategory
from ls.cognition.state_tracker import AgentState


def _goal(goal_id: str, priority: float, category: NeedCategory) -> AgentGoal:
    return AgentGoal(
        id=goal_id,
        description=goal_id,
        linked_needs=[AgentNeed(id=f"need-{goal_id}", description=category.value, intensity=0.7, satisfaction=0.2, category=category)],
        priority=priority,
        base_priority=priority,
        emotional_weight=1.0,
    )


def test_counterfactual_engine_evaluates_alternative_goals() -> None:
    engine = CounterfactualEngine()
    state = AgentState(goal="goal-learning", context={"stress": 0.3}, progress_score=0.2, goal_completion=0.1)
    chosen_goal = _goal("goal-learning", 0.6, NeedCategory.LEARNING)
    alternatives = [
        _goal("goal-safety", 0.9, NeedCategory.SURVIVAL),
        _goal("goal-social", 0.5, NeedCategory.SOCIAL),
    ]

    outcomes = engine.evaluate(state, chosen_goal, alternatives)

    assert [item.goal_id for item in outcomes] == ["goal-safety", "goal-social"]
    assert all(0.0 <= item.predicted_effect <= 1.0 for item in outcomes)
    assert all(0.0 <= item.predicted_cost <= 1.0 for item in outcomes)
    assert all(isinstance(item.category_effects, dict) for item in outcomes)
    assert all(NeedCategory.SURVIVAL.value in item.category_effects or NeedCategory.SOCIAL.value in item.category_effects for item in outcomes)
    assert outcomes[0].predicted_effect > outcomes[1].predicted_effect



def test_counterfactual_engine_applies_interference_for_same_category() -> None:
    engine = CounterfactualEngine()
    state = AgentState(goal="goal-a", context={"stress": 0.1}, progress_score=0.0, goal_completion=0.0)
    chosen_goal = _goal("goal-a", 0.7, NeedCategory.SURVIVAL)
    alternatives = [
        _goal("goal-b", 0.8, NeedCategory.SURVIVAL),
        _goal("goal-c", 0.7, NeedCategory.SURVIVAL),
    ]

    outcomes = engine.evaluate(state, chosen_goal, alternatives)

    for outcome in outcomes:
        assert outcome.category_effects[NeedCategory.SURVIVAL.value] < outcome.predicted_effect
