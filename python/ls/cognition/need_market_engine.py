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
    expected_effect: float
    cost: float
    priority: float
    capability_ids: tuple[str, ...]
    strategy_idea_id: str
    contract_node_id: str | None = None

    @property
    def capability_id(self) -> str:
        return self.capability_ids[0]


class NeedMarketEngine:
    def __init__(self, memory_graph: MemoryGraph):
        self.memory_graph = memory_graph
        self.synergy_engine = StrategySynergyEngine(memory_graph)

    def match(self, needs: list["AgentNeed"], capabilities: list[Capability], max_contracts: int = 3) -> list[GoalContract]:
        if not capabilities:
            return []

        ideas_by_need = self.synergy_engine.generate_strategy_ideas(needs, capabilities, top_k=max_contracts)
        contracts: list[GoalContract] = []

        for need in needs:
            best_idea = self._best_idea_for_need(ideas_by_need.get(need.id, []))
            if best_idea is None:
                continue

            capability_ids = tuple(cap.id for cap in best_idea.capability_set.capabilities)
            if not capability_ids:
                continue

            score = need.intensity * best_idea.expected_effect
            cost_sum = sum(cap.cost for cap in best_idea.capability_set.capabilities)
            priority = score - cost_sum

            base_contract = GoalContract(
                id=f"contract-{need.id}-{'-'.join(capability_ids)}",
                need_id=need.id,
                expected_effect=best_idea.expected_effect,
                cost=cost_sum,
                priority=priority,
                capability_ids=capability_ids,
                strategy_idea_id=best_idea.id,
            )
            contract_node_id = self._record_contract_chain(base_contract)
            contracts.append(
                GoalContract(
                    id=base_contract.id,
                    need_id=base_contract.need_id,
                    expected_effect=base_contract.expected_effect,
                    cost=base_contract.cost,
                    priority=base_contract.priority,
                    capability_ids=base_contract.capability_ids,
                    strategy_idea_id=base_contract.strategy_idea_id,
                    contract_node_id=contract_node_id,
                )
            )

        contracts.sort(key=lambda item: item.priority, reverse=True)
        return contracts[:max_contracts]

    @staticmethod
    def build_strategy(contract: GoalContract, goal: "AgentGoal") -> "Strategy":
        """Build a capability-aware strategy; TODO: replace with richer planning policy."""
        from ls.cognition.motivation_engine import Strategy

        steps = [f"assess_need:{contract.need_id}"]
        steps.extend(f"apply_capability:{capability_id}" for capability_id in contract.capability_ids)
        steps.append(f"verify_result:{goal.id}")
        return Strategy(goal=goal, steps=steps)

    @staticmethod
    def _best_idea_for_need(ideas):
        return ideas[0] if ideas else None

    def _record_contract_chain(self, contract: GoalContract) -> str:
        contract_node = self.memory_graph.add_node(
            node_type="goal_contract",
            content={
                "contract_id": contract.id,
                "need_id": contract.need_id,
                "capability_id": contract.capability_id,
                "capability_ids": list(contract.capability_ids),
                "strategy_idea_id": contract.strategy_idea_id,
                "expected_effect": contract.expected_effect,
                "cost": contract.cost,
                "priority": contract.priority,
            },
        )

        idea_node_id = self._find_strategy_idea_node(contract.strategy_idea_id)
        if idea_node_id is not None:
            self.memory_graph.add_edge(MemoryEdge(idea_node_id, contract_node.node_id, "forms", contract.priority))

        return contract_node.node_id

    def _find_strategy_idea_node(self, strategy_idea_id: str) -> str | None:
        node = self.memory_graph.find_first_node(node_type="strategy_idea", content_key="idea_id", content_value=strategy_idea_id)
        return node.node_id if node else None
