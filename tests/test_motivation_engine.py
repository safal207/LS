from __future__ import annotations

import pytest

from ls.cognition.motivation_engine import ActionOutcome, AgentNeed, EmotionalState, MotivationEngine
from ls.memory.memory_graph import MemoryGraph


class _Executor:
    def execute(self, step: str, goal):
        if step.startswith("execute") or "apply_capability" in step:
            return ActionOutcome(success=True, effect=0.2, details="ok")
        return ActionOutcome(success=True, effect=0.05, details="minor")


def test_motivation_engine_generates_goals_from_needs_priority():
    engine = MotivationEngine(MemoryGraph(), _Executor())
    needs = [
        AgentNeed(id="social", description="social connection", intensity=0.3, satisfaction=0.8),
        AgentNeed(id="learning", description="learning", intensity=0.8, satisfaction=0.1),
    ]

    goals, contract_map = engine.generate_goals(needs)

    assert goals[0].id == "goal-learning"
    assert goals[0].priority > goals[1].priority
    assert contract_map == {}


def test_motivation_engine_cycle_updates_needs_and_memory_graph_chain():
    graph = MemoryGraph()
    engine = MotivationEngine(graph, _Executor())
    need = AgentNeed(id="energy", description="energy restoration", intensity=0.7, satisfaction=0.2)

    outcomes = engine.run_cycle([need], max_goals=1)

    assert len(outcomes) == 3
    assert need.satisfaction > 0.2
    assert need.intensity < 0.7

    relations = {(edge.relation, graph.get_node(edge.source).node_type, graph.get_node(edge.target).node_type) for edge in graph.edges}
    assert ("generates", "need", "goal") in relations
    assert ("produces", "goal", "strategy") in relations
    assert ("executes", "strategy", "action") in relations
    assert ("leads_to", "action", "outcome") in relations
    assert ("updates", "outcome", "reflection") in relations


def test_motivation_engine_reuses_need_nodes_across_cycles():
    graph = MemoryGraph()
    engine = MotivationEngine(graph, _Executor())
    need = AgentNeed(id="energy", description="energy restoration", intensity=0.6, satisfaction=0.3)

    engine.run_cycle([need], max_goals=1)
    engine.run_cycle([need], max_goals=1)

    need_nodes = [n for n in graph.nodes.values() if n.node_type == "need" and n.content.get("need_id") == "energy"]
    assert len(need_nodes) == 1


def test_motivation_engine_emotional_weight_raises_safety_priority_under_stress():
    engine = MotivationEngine(MemoryGraph(), _Executor())
    needs = [
        AgentNeed(id="learning", description="learning", intensity=0.8, satisfaction=0.1),
        AgentNeed(id="safety", description="safety", intensity=0.6, satisfaction=0.1),
    ]

    calm_goals, _ = engine.generate_goals(needs, emotional_state=EmotionalState(stress=0.0))
    stressed_goals, _ = engine.generate_goals(needs, emotional_state=EmotionalState(stress=0.9))

    calm_top_goal = calm_goals[0]
    stressed_top_goal = stressed_goals[0]
    assert calm_top_goal.id == "goal-learning"
    assert stressed_top_goal.id == "goal-safety"


def test_motivation_engine_persists_emotional_weight_in_goal_memory_node():
    graph = MemoryGraph()
    engine = MotivationEngine(graph, _Executor())
    need = AgentNeed(id="safety", description="safety", intensity=0.6, satisfaction=0.1)

    engine.run_cycle([need], max_goals=1, emotional_state=EmotionalState(stress=1.0))

    goal_nodes = [node for node in graph.nodes.values() if node.node_type == "goal" and node.content.get("goal_id") == "goal-safety"]
    assert len(goal_nodes) == 1
    goal_content = goal_nodes[0].content
    assert goal_content["base_priority"] == pytest.approx(0.6175)
    assert goal_content["emotional_weight"] == pytest.approx(1.8)
    assert goal_content["priority"] == pytest.approx(1.1115)
