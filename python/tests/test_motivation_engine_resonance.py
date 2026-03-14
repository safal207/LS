import pytest

from ls.cognition.agent_identity import AgentIdentity
from ls.cognition.counterfactual_engine import CounterfactualOutcome
from ls.cognition.motivation_engine import (
    ActionOutcome,
    AgentGoal,
    AgentNeed,
    EmotionalState,
    MotivationEngine,
    NeedCategory,
)
from ls.memory.memory_graph import MemoryGraph


class StubExecutor:
    def execute(self, step: str, goal: AgentGoal) -> ActionOutcome:
        return ActionOutcome(success=True, effect=0.4, details=f"ok:{step}:{goal.id}")


def test_run_cycle_updates_resonance_map_and_simulated_identity() -> None:
    graph = MemoryGraph()
    identity = AgentIdentity(id="id-1", learning_rate=0.1)
    engine = MotivationEngine(memory_graph=graph, executor=StubExecutor(), identity=identity)

    needs = [
        AgentNeed("learn", "learning loop", intensity=0.9, satisfaction=0.1, category=NeedCategory.LEARNING),
        AgentNeed("social", "social sync", intensity=0.85, satisfaction=0.1, category=NeedCategory.SOCIAL),
    ]

    def fake_evaluate(state, chosen_goal, alternative_goals):
        _ = state
        return [
            CounterfactualOutcome(
                goal_id=alternative_goals[0].id,
                predicted_effect=0.7,
                predicted_cost=0.2,
                category_effects={NeedCategory.LEARNING.value: 0.6},
            )
        ]

    engine.counterfactual_engine.evaluate = fake_evaluate  # type: ignore[method-assign]

    outcomes = engine.run_cycle(needs, max_goals=2, emotional_state=EmotionalState(stress=0.2))

    assert outcomes
    assert engine.resonance_map
    assert any(category == NeedCategory.LEARNING.value for (_, category) in engine.resonance_map)

    report = engine.identity_update_report()
    assert any(entry["mode"] == "simulated" for entry in report)


def test_rank_uses_resonance_map_synergy() -> None:
    graph = MemoryGraph()
    engine = MotivationEngine(memory_graph=graph, executor=StubExecutor())

    need1 = AgentNeed("n1", "learning", intensity=0.6, satisfaction=0.1, category=NeedCategory.LEARNING)
    need2 = AgentNeed("n2", "learning", intensity=0.6, satisfaction=0.1, category=NeedCategory.LEARNING)

    goal1 = AgentGoal("g1", "goal1", [need1], priority=0.5, base_priority=0.5, emotional_weight=1.0)
    goal2 = AgentGoal("g2", "goal2", [need2], priority=0.5, base_priority=0.5, emotional_weight=1.0)

    engine.resonance_map[("g1", NeedCategory.LEARNING.value)] = 1.0
    engine.resonance_map[("g2", NeedCategory.LEARNING.value)] = 0.0

    ranked = engine._rank_goals_with_counterfactual_potential([goal1, goal2], EmotionalState(stress=0.0))

    assert ranked[0].id == "g1"


def test_resonance_strength_helpers_accumulate_goal_categories() -> None:
    graph = MemoryGraph()
    engine = MotivationEngine(memory_graph=graph, executor=StubExecutor())

    learning = AgentNeed("n1", "learning", intensity=0.6, satisfaction=0.1, category=NeedCategory.LEARNING)
    social = AgentNeed("n2", "social", intensity=0.6, satisfaction=0.1, category=NeedCategory.SOCIAL)
    goal = AgentGoal("g1", "goal", [learning, social], priority=0.5, base_priority=0.5, emotional_weight=1.0)

    engine.resonance_map[("g1", NeedCategory.LEARNING.value)] = 0.25
    engine.resonance_map[("g1", NeedCategory.SOCIAL.value)] = 0.35

    assert engine.resonance_strength_for_goal(goal) == pytest.approx(0.6)
    assert engine.resonance_strengths_for_goals([goal]) == {"g1": pytest.approx(0.6)}


def test_cognitive_momentum_update_and_decay() -> None:
    graph = MemoryGraph()
    engine = MotivationEngine(memory_graph=graph, executor=StubExecutor())

    assert engine.momentum_for_goal("g1") == 0.0

    engine.momentum_engine.update("g1", True)
    assert engine.momentum_for_goal("g1") == pytest.approx(0.3)

    engine.momentum_engine.update("g1", True)
    assert engine.momentum_for_goal("g1") == pytest.approx(0.54)

    engine.momentum_engine.update("g1", False)
    assert engine.momentum_for_goal("g1") == pytest.approx(0.324)


def test_rank_uses_momentum_bonus() -> None:
    graph = MemoryGraph()
    engine = MotivationEngine(memory_graph=graph, executor=StubExecutor())

    need = AgentNeed("n", "learning", intensity=0.6, satisfaction=0.1, category=NeedCategory.LEARNING)
    goal1 = AgentGoal("g1", "goal1", [need], priority=0.5, base_priority=0.5, emotional_weight=1.0)
    goal2 = AgentGoal("g2", "goal2", [need], priority=0.5, base_priority=0.5, emotional_weight=1.0)

    engine.momentum_engine.goal_momentum["g1"] = 1.0
    engine.momentum_engine.goal_momentum["g2"] = 0.0

    ranked = engine._rank_goals_with_counterfactual_potential([goal1, goal2], EmotionalState(stress=0.0))

    assert ranked[0].id == "g1"


def test_run_cycle_updates_momentum_once_per_goal() -> None:
    graph = MemoryGraph()
    engine = MotivationEngine(memory_graph=graph, executor=StubExecutor())

    needs = [
        AgentNeed("learn", "learning loop", intensity=0.9, satisfaction=0.1, category=NeedCategory.LEARNING),
        AgentNeed("social", "social sync", intensity=0.85, satisfaction=0.1, category=NeedCategory.SOCIAL),
    ]

    goals, _ = engine.generate_goals(needs, max_goals=2)
    top_goal_id = goals[0].id

    engine.run_cycle(needs, max_goals=2, emotional_state=EmotionalState(stress=0.2))

    # Momentum updates once per goal (not once per step), so first successful goal lands at 0.3.
    assert engine.momentum_for_goal(top_goal_id) == pytest.approx(0.3)


def test_momentum_decay_applies_each_cycle() -> None:
    graph = MemoryGraph()
    engine = MotivationEngine(memory_graph=graph, executor=StubExecutor())
    engine.momentum_engine.goal_momentum["g1"] = 1.0

    engine.momentum_engine.decay()

    assert engine.momentum_for_goal("g1") == pytest.approx(0.95)


def test_goal_attractor_field_updates_from_coactivation() -> None:
    graph = MemoryGraph()
    engine = MotivationEngine(memory_graph=graph, executor=StubExecutor())

    needs = [
        AgentNeed("learn", "learning loop", intensity=0.9, satisfaction=0.1, category=NeedCategory.LEARNING),
        AgentNeed("social", "social sync", intensity=0.85, satisfaction=0.1, category=NeedCategory.SOCIAL),
    ]

    goals, _ = engine.generate_goals(needs, max_goals=2)
    goal_ids = [goal.id for goal in goals]

    engine.attractor_field.update(goal_ids)

    assert engine.attractor_field.influence(goal_ids[0], goal_ids[1]) == pytest.approx(0.1)
    assert engine.attractor_field.influence(goal_ids[1], goal_ids[0]) == pytest.approx(0.1)


def test_rank_uses_attractor_bonus_from_recent_goals() -> None:
    graph = MemoryGraph()
    engine = MotivationEngine(memory_graph=graph, executor=StubExecutor())

    need = AgentNeed("n", "learning", intensity=0.6, satisfaction=0.1, category=NeedCategory.LEARNING)
    goal1 = AgentGoal("g1", "goal1", [need], priority=0.5, base_priority=0.5, emotional_weight=1.0)
    goal2 = AgentGoal("g2", "goal2", [need], priority=0.5, base_priority=0.5, emotional_weight=1.0)

    engine.recent_goals = ["g1"]
    engine.attractor_field.goal_goal[("g1", "g2")] = 1.0

    ranked = engine._rank_goals_with_counterfactual_potential([goal1, goal2], EmotionalState(stress=0.0))

    assert ranked[0].id == "g2"


def test_run_cycle_persists_recent_goals_for_attractor() -> None:
    graph = MemoryGraph()
    engine = MotivationEngine(memory_graph=graph, executor=StubExecutor())

    needs = [
        AgentNeed("learn", "learning loop", intensity=0.9, satisfaction=0.1, category=NeedCategory.LEARNING),
        AgentNeed("social", "social sync", intensity=0.85, satisfaction=0.1, category=NeedCategory.SOCIAL),
    ]

    engine.run_cycle(needs, max_goals=2, emotional_state=EmotionalState(stress=0.2))

    assert len(engine.recent_goals) == 2
    assert all(goal_id.startswith("goal-") for goal_id in engine.recent_goals)
