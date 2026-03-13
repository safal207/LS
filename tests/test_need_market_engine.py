from __future__ import annotations

from ls.cognition.motivation_engine import ActionOutcome, AgentNeed, EmotionalState, MotivationEngine, NeedCategory
from ls.cognition.need_market_engine import Capability, NeedMarketEngine
from ls.memory.memory_graph import MemoryGraph


class _Executor:
    def execute(self, step: str, goal):
        if "apply_capability" in step:
            return ActionOutcome(success=True, effect=0.25, details="capability_applied")
        return ActionOutcome(success=True, effect=0.05, details="progress")


def test_need_market_uses_synergy_and_may_select_multiple_capabilities():
    graph = MemoryGraph()
    market = NeedMarketEngine(graph)

    needs = [AgentNeed(id="research", description="research gap", intensity=0.9, satisfaction=0.1)]
    capabilities = [
        Capability(id="search_information", description="search", effectiveness=0.7, cost=0.1),
        Capability(id="query_api", description="api", effectiveness=0.9, cost=0.05),
    ]

    contracts = market.match(needs, capabilities)

    assert len(contracts) == 1
    assert set(contracts[0].capability_ids) == {"search_information", "query_api"}


def test_need_market_chain_is_recorded_in_memory_graph_and_motivation_cycle():
    graph = MemoryGraph()
    engine = MotivationEngine(graph, _Executor())

    needs = [AgentNeed(id="analysis", description="deep analysis", intensity=0.8, satisfaction=0.2)]
    capabilities = [
        Capability(id="run_analysis", description="analysis tool", effectiveness=0.8, cost=0.1),
        Capability(id="search_information", description="search", effectiveness=0.6, cost=0.05),
    ]

    outcomes = engine.run_cycle(needs, max_goals=1, capabilities=capabilities)

    assert len(outcomes) >= 3
    relations = {(edge.relation, graph.get_node(edge.source).node_type, graph.get_node(edge.target).node_type) for edge in graph.edges}

    assert ("inspires", "need", "strategy_idea") in relations
    assert ("uses", "strategy_idea", "capability") in relations
    assert ("forms", "strategy_idea", "goal_contract") in relations
    assert ("produces", "goal_contract", "strategy") in relations
    assert ("executes", "strategy", "action") in relations
    assert ("leads_to", "action", "outcome") in relations
    assert ("updates", "outcome", "reflection") in relations
    assert ("updates", "reflection", "need") in relations


def test_need_market_contract_priority_is_emotionally_modulated():
    graph = MemoryGraph()
    engine = MotivationEngine(graph, _Executor())

    needs = [
        AgentNeed(id="safe", description="safe", intensity=0.8, satisfaction=0.1, category=NeedCategory.SURVIVAL),
        AgentNeed(id="learn", description="learn", intensity=0.8, satisfaction=0.1, category=NeedCategory.LEARNING),
    ]
    capabilities = [
        Capability(id="same_tool", description="same", effectiveness=0.8, cost=0.1),
    ]

    calm_goals, _ = engine.generate_goals(needs, max_goals=2, capabilities=capabilities, emotional_state=EmotionalState(stress=0.0))
    stressed_goals, _ = engine.generate_goals(needs, max_goals=2, capabilities=capabilities, emotional_state=EmotionalState(stress=1.0))

    calm = {goal.linked_needs[0].id: goal for goal in calm_goals}
    stressed = {goal.linked_needs[0].id: goal for goal in stressed_goals}

    assert calm["safe"].emotional_weight == 1.0
    assert stressed["safe"].emotional_weight == 1.8
    assert stressed["safe"].priority > calm["safe"].priority

    assert calm["learn"].emotional_weight == 1.0
    assert stressed["learn"].emotional_weight == 0.5
    assert stressed["learn"].priority < calm["learn"].priority
