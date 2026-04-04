from __future__ import annotations

from ls.cognition.motivation_engine import AgentNeed
from ls.cognition.need_market_engine import Capability
from ls.cognition.strategy_synergy_engine import StrategySynergyEngine
from ls.memory.memory_graph import MemoryGraph


def test_strategy_synergy_generates_single_pair_and_triplet_ideas():
    graph = MemoryGraph()
    engine = StrategySynergyEngine(graph)

    needs = [AgentNeed(id="research", description="research", intensity=0.8, satisfaction=0.2)]
    capabilities = [
        Capability(id="A", description="A", effectiveness=0.4, cost=0.05),
        Capability(id="B", description="B", effectiveness=0.5, cost=0.05),
        Capability(id="C", description="C", effectiveness=0.6, cost=0.05),
    ]

    ideas = engine.generate_strategy_ideas(needs, capabilities, top_k=20)["research"]
    ids = {idea.id for idea in ideas}

    assert "idea-research-A" in ids
    assert "idea-research-A-B" in ids
    assert "idea-research-A-B-C" in ids


def test_strategy_synergy_selects_highest_score_idea_first():
    graph = MemoryGraph()
    engine = StrategySynergyEngine(graph)

    needs = [AgentNeed(id="n", description="need", intensity=1.0, satisfaction=0.0)]
    capabilities = [
        Capability(id="low", description="low", effectiveness=0.2, cost=0.2),
        Capability(id="high", description="high", effectiveness=0.8, cost=0.05),
    ]

    ideas = engine.generate_strategy_ideas(needs, capabilities, top_k=3)["n"]

    assert ideas[0].score >= ideas[1].score


def test_strategy_synergy_records_memory_graph_relations():
    graph = MemoryGraph()
    engine = StrategySynergyEngine(graph)

    needs = [AgentNeed(id="memory", description="memory", intensity=0.7, satisfaction=0.1)]
    capabilities = [Capability(id="cap", description="cap", effectiveness=0.7, cost=0.1)]

    engine.generate_strategy_ideas(needs, capabilities, top_k=1)

    relations = {(edge.relation, graph.get_node(edge.source).node_type, graph.get_node(edge.target).node_type) for edge in graph.edges}
    assert ("inspires", "need", "strategy_idea") in relations
    assert ("uses", "strategy_idea", "capability") in relations
