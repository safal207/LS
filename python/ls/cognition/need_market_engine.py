from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ls.cognition.motivation_engine import AgentNeed, AgentGoal, Strategy
from ls.memory.edge import MemoryEdge
from ls.memory.memory_graph import MemoryGraph


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


class NeedMarketEngine:
    def __init__(self, memory_graph: MemoryGraph):
        self.memory_graph = memory_graph

    def match(self, needs: list["AgentNeed"], capabilities: list[Capability], max_contracts: int = 3) -> list[GoalContract]:
        contracts: list[GoalContract] = []

        for need in needs:
            if not capabilities:
                continue

            best_capability = max(
                capabilities,
                key=lambda capability: (need.intensity * capability.effectiveness) - capability.cost,
            )

            score = need.intensity * best_capability.effectiveness
            priority = score - best_capability.cost
            contract = GoalContract(
                id=f"contract-{need.id}-{best_capability.id}",
                need_id=need.id,
                capability_id=best_capability.id,
                expected_effect=best_capability.effectiveness,
                cost=best_capability.cost,
                priority=priority,
            )
            contracts.append(contract)
            self._record_contract_chain(need, best_capability, contract)

        contracts.sort(key=lambda item: item.priority, reverse=True)
        return contracts[:max_contracts]

    @staticmethod
    def build_strategy(contract: GoalContract, goal: "AgentGoal") -> "Strategy":
        from ls.cognition.motivation_engine import Strategy

        steps = [
            f"assess_need:{contract.need_id}",
            f"apply_capability:{contract.capability_id}",
            f"verify_result:{goal.id}",
        ]
        return Strategy(goal=goal, steps=steps)

    def _record_contract_chain(self, need: "AgentNeed", capability: Capability, contract: GoalContract) -> None:
        need_node = self.memory_graph.add_node(
            node_type="need",
            content={
                "need_id": need.id,
                "description": need.description,
                "intensity": need.intensity,
                "satisfaction": need.satisfaction,
            },
        )
        capability_node = self.memory_graph.add_node(
            node_type="capability",
            content={
                "capability_id": capability.id,
                "description": capability.description,
                "effectiveness": capability.effectiveness,
                "cost": capability.cost,
            },
        )
        contract_node = self.memory_graph.add_node(
            node_type="goal_contract",
            content={
                "contract_id": contract.id,
                "need_id": contract.need_id,
                "capability_id": contract.capability_id,
                "expected_effect": contract.expected_effect,
                "cost": contract.cost,
                "priority": contract.priority,
            },
        )

        self.memory_graph.add_edge(MemoryEdge(need_node.node_id, capability_node.node_id, "requests", contract.priority))
        self.memory_graph.add_edge(MemoryEdge(capability_node.node_id, contract_node.node_id, "forms", contract.priority))
