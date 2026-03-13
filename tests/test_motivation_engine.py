from __future__ import annotations

from ls.cognition.motivation_engine import ActionOutcome, AgentNeed, MotivationEngine
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
