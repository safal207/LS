from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ls.cognition.strategy_synergy_engine import StrategySynergyEngine
from ls.memory.edge import MemoryEdge
from ls.memory.memory_graph import MemoryGraph

if TYPE_CHECKING:
    from ls.cognition.motivation_engine import AgentGoal, AgentNeed, Strategy


@dataclass(frozen=True)
class Capability:
    id: str
    description: str
    effectiveness: float
    cost: float


@dataclass(frozen=True)
class GoalContract:
    id: str
    need_id: str
    capability_id: str
    expected_effect: float
    cost: float
    priority: float
    capability_ids: list[str]
    strategy_idea_id: str


class NeedMarketEngine:
    def __init__(self, memory_graph: MemoryGraph):
        self.memory_graph = memory_graph
        self.synergy_engine = StrategySynergyEngine(memory_graph)

    def match(self, needs: list["AgentNeed"], capabilities: list[Capability], max_contracts: int = 3) -> list[GoalContract]:
        contracts: list[GoalContract] = []
        if not capabilities:
            return contracts

        ideas_by_need = self.synergy_engine.generate_strategy_ideas(needs, capabilities, top_k=max_contracts)

        for need in needs:
            ideas = ideas_by_need.get(need.id, [])
            if not ideas:
                continue

            best_idea = ideas[0]
            capability_ids = [cap.id for cap in best_idea.capability_set.capabilities]
            score = need.intensity * best_idea.expected_effect
            cost_sum = sum(cap.cost for cap in best_idea.capability_set.capabilities)
            priority = score - cost_sum
            primary_capability_id = capability_ids[0]

            contract = GoalContract(
                id=f"contract-{need.id}-{'-'.join(capability_ids)}",
                need_id=need.id,
                capability_id=primary_capability_id,
                expected_effect=best_idea.expected_effect,
                cost=cost_sum,
                priority=priority,
                capability_ids=capability_ids,
                strategy_idea_id=best_idea.id,
            )
            contracts.append(contract)
            self._record_contract_chain(contract)

        contracts.sort(key=lambda item: item.priority, reverse=True)
        return contracts[:max_contracts]

    @staticmethod
    def build_strategy(contract: GoalContract, goal: "AgentGoal") -> "Strategy":
        from ls.cognition.motivation_engine import Strategy

        steps = [f"assess_need:{contract.need_id}"]
        steps.extend(f"apply_capability:{capability_id}" for capability_id in contract.capability_ids)
        steps.append(f"verify_result:{goal.id}")
        return Strategy(goal=goal, steps=steps)

    def _record_contract_chain(self, contract: GoalContract) -> None:
        contract_node = self.memory_graph.add_node(
            node_type="goal_contract",
            content={
                "contract_id": contract.id,
                "need_id": contract.need_id,
                "capability_id": contract.capability_id,
                "capability_ids": contract.capability_ids,
                "strategy_idea_id": contract.strategy_idea_id,
                "expected_effect": contract.expected_effect,
                "cost": contract.cost,
                "priority": contract.priority,
            },
        )

        idea_node_id = self._find_strategy_idea_node(contract.strategy_idea_id)
        if idea_node_id is not None:
            self.memory_graph.add_edge(MemoryEdge(idea_node_id, contract_node.node_id, "forms", contract.priority))

    def _find_strategy_idea_node(self, strategy_idea_id: str) -> str | None:
        for node in self.memory_graph.nodes.values():
            if node.node_type != "strategy_idea":
                continue
            if node.content.get("idea_id") == strategy_idea_id:
                return node.node_id
        return None
