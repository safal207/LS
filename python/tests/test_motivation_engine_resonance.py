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
