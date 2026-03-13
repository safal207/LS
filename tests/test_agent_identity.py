from __future__ import annotations

import pytest

from ls.cognition import AgentIdentity
from ls.cognition.motivation_engine import ActionOutcome, AgentNeed, EmotionalState, MotivationEngine, NeedCategory
from ls.cognition.need_market_engine import Capability
from ls.memory.memory_graph import MemoryGraph


class _SuccessfulExecutor:
    def execute(self, step: str, goal):
        return ActionOutcome(success=True, effect=0.2, details="ok")


class _FailingExecutor:
    def execute(self, step: str, goal):
        return ActionOutcome(success=False, effect=0.2, details="no")


def _base_needs() -> list[AgentNeed]:
    return [
        AgentNeed(id="safe", description="safety", intensity=0.7, satisfaction=0.2, category=NeedCategory.SURVIVAL),
        AgentNeed(id="learn", description="learning", intensity=0.7, satisfaction=0.2, category=NeedCategory.LEARNING),
    ]


def test_identity_values_change_goal_priorities_for_same_needs_and_stress():
    needs = _base_needs()
    surv_identity = AgentIdentity(id="a", values={NeedCategory.SURVIVAL.value: 1.5, NeedCategory.LEARNING.value: 0.6})
    learn_identity = AgentIdentity(id="b", values={NeedCategory.SURVIVAL.value: 0.6, NeedCategory.LEARNING.value: 1.5})

    surv_engine = MotivationEngine(MemoryGraph(), _SuccessfulExecutor(), identity=surv_identity)
    learn_engine = MotivationEngine(MemoryGraph(), _SuccessfulExecutor(), identity=learn_identity)

    surv_goals, _ = surv_engine.generate_goals(needs, emotional_state=EmotionalState(stress=0.4))
    learn_goals, _ = learn_engine.generate_goals(_base_needs(), emotional_state=EmotionalState(stress=0.4))

    assert surv_goals[0].id == "goal-safe"
    assert learn_goals[0].id == "goal-learn"


def test_high_survival_identity_amplifies_survival_priority():
    needs = _base_needs()
    base_engine = MotivationEngine(MemoryGraph(), _SuccessfulExecutor())
    tuned_engine = MotivationEngine(
        MemoryGraph(),
        _SuccessfulExecutor(),
        identity=AgentIdentity(id="s", values={NeedCategory.SURVIVAL.value: 1.8}),
    )

    base_goals, _ = base_engine.generate_goals(_base_needs(), emotional_state=EmotionalState(stress=0.8))
    tuned_goals, _ = tuned_engine.generate_goals(needs, emotional_state=EmotionalState(stress=0.8))

    base_safe = next(goal for goal in base_goals if goal.id == "goal-safe")
    tuned_safe = next(goal for goal in tuned_goals if goal.id == "goal-safe")
    assert tuned_safe.priority > base_safe.priority


def test_low_learning_identity_suppresses_learning_even_under_zero_stress():
    engine = MotivationEngine(
        MemoryGraph(),
        _SuccessfulExecutor(),
        identity=AgentIdentity(id="low-learning", values={NeedCategory.LEARNING.value: 0.1}),
    )
    learning = AgentNeed(id="learn", description="learning", intensity=0.9, satisfaction=0.0, category=NeedCategory.LEARNING)
    survival = AgentNeed(id="safe", description="safety", intensity=0.5, satisfaction=0.0, category=NeedCategory.SURVIVAL)

    goals, _ = engine.generate_goals([learning, survival], emotional_state=EmotionalState(stress=0.0))
    assert goals[0].id == "goal-safe"


def test_identity_values_increase_after_successful_outcomes():
    identity = AgentIdentity(id="inc", values={NeedCategory.SURVIVAL.value: 0.5}, learning_rate=0.01)
    engine = MotivationEngine(MemoryGraph(), _SuccessfulExecutor(), identity=identity)

    engine.run_cycle([AgentNeed(id="safe", description="safety", intensity=0.7, satisfaction=0.2, category=NeedCategory.SURVIVAL)])

    assert identity.values[NeedCategory.SURVIVAL.value] > 0.5


def test_identity_values_decrease_after_failed_outcomes():
    identity = AgentIdentity(id="dec", values={NeedCategory.SURVIVAL.value: 0.8}, learning_rate=0.01)
    engine = MotivationEngine(MemoryGraph(), _FailingExecutor(), identity=identity)

    engine.run_cycle([AgentNeed(id="safe", description="safety", intensity=0.7, satisfaction=0.2, category=NeedCategory.SURVIVAL)])

    assert identity.values[NeedCategory.SURVIVAL.value] < 0.8


def test_identity_changes_are_small_per_cycle():
    identity = AgentIdentity(id="small", values={NeedCategory.SURVIVAL.value: 0.5}, learning_rate=0.01)
    engine = MotivationEngine(MemoryGraph(), _SuccessfulExecutor(), identity=identity)

    before = identity.values[NeedCategory.SURVIVAL.value]
    engine.run_cycle([AgentNeed(id="safe", description="safety", intensity=0.7, satisfaction=0.2, category=NeedCategory.SURVIVAL)])
    after = identity.values[NeedCategory.SURVIVAL.value]

    assert (after - before) < (identity.learning_rate * 2)


def test_identity_alignment_persisted_in_goal_node_content_in_contract_path():
    graph = MemoryGraph()
    identity = AgentIdentity(id="persist", values={NeedCategory.SURVIVAL.value: 1.4})
    engine = MotivationEngine(graph, _SuccessfulExecutor(), identity=identity)
    need = AgentNeed(id="safe", description="safety", intensity=0.8, satisfaction=0.1, category=NeedCategory.SURVIVAL)
    capability = Capability(id="shield", description="shield", effectiveness=0.9, cost=0.1)

    engine.run_cycle([need], max_goals=1, capabilities=[capability], emotional_state=EmotionalState(stress=0.6))

    goal_nodes = [node for node in graph.nodes.values() if node.node_type == "goal" and node.content.get("goal_id", "").startswith("goal-contract-")]
    assert len(goal_nodes) == 1
    goal_content = goal_nodes[0].content
    assert goal_content["identity_alignment"] == pytest.approx(1.4)
