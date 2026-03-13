from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import TYPE_CHECKING

from ls.memory.edge import MemoryEdge
from ls.memory.memory_graph import MemoryGraph

if TYPE_CHECKING:
    from ls.cognition.motivation_engine import AgentNeed
    from ls.cognition.need_market_engine import Capability


@dataclass(frozen=True)
class CapabilitySet:
    capabilities: list["Capability"]
    synergy_score: float


@dataclass(frozen=True)
class StrategyIdea:
    id: str
    need_id: str
    capability_set: CapabilitySet
    expected_effect: float
    score: float


class StrategySynergyEngine:
    def __init__(self, memory_graph: MemoryGraph, max_combination_size: int = 3, synergy_factor: float = 0.1):
        self.memory_graph = memory_graph
        self.max_combination_size = max_combination_size
        self.synergy_factor = synergy_factor

    def generate_strategy_ideas(
        self,
        needs: list["AgentNeed"],
        capabilities: list["Capability"],
        top_k: int = 3,
    ) -> dict[str, list[StrategyIdea]]:
        ideas_by_need: dict[str, list[StrategyIdea]] = {}
        if not capabilities:
            return ideas_by_need

        need_nodes = self._find_or_create_need_nodes(needs)

        for need in needs:
            all_ideas: list[StrategyIdea] = []
            max_size = min(self.max_combination_size, len(capabilities))
            for size in range(1, max_size + 1):
                for subset in combinations(capabilities, size):
                    subset_list = list(subset)
                    all_ideas.append(self._build_idea(need, subset_list))

            all_ideas.sort(key=lambda idea: idea.score, reverse=True)
            selected = all_ideas[:top_k]
            ideas_by_need[need.id] = selected

            for idea in selected:
                self._record_idea(need_nodes.get(need.id), idea)

        return ideas_by_need

    def _build_idea(self, need: "AgentNeed", capabilities: list["Capability"]) -> StrategyIdea:
        effectiveness_sum = sum(cap.effectiveness for cap in capabilities)
        synergy_bonus = self.synergy_factor * len(capabilities)
        cost_sum = sum(cap.cost for cap in capabilities)
        score = need.intensity * (effectiveness_sum + synergy_bonus) - cost_sum
        expected_effect = min(1.0, (effectiveness_sum + synergy_bonus) / max(len(capabilities), 1))

        capability_set = CapabilitySet(capabilities=capabilities, synergy_score=effectiveness_sum + synergy_bonus)
        caps_suffix = "-".join(cap.id for cap in capabilities)
        return StrategyIdea(
            id=f"idea-{need.id}-{caps_suffix}",
            need_id=need.id,
            capability_set=capability_set,
            expected_effect=expected_effect,
            score=score,
        )

    def _record_idea(self, need_node_id: str | None, idea: StrategyIdea) -> None:
        capability_set_node = self.memory_graph.add_node(
            node_type="capability_set",
            content={
                "capability_ids": [cap.id for cap in idea.capability_set.capabilities],
                "synergy_score": idea.capability_set.synergy_score,
            },
        )
        idea_node = self.memory_graph.add_node(
            node_type="strategy_idea",
            content={
                "idea_id": idea.id,
                "need_id": idea.need_id,
                "expected_effect": idea.expected_effect,
                "score": idea.score,
            },
        )

        self.memory_graph.add_edge(MemoryEdge(idea_node.node_id, capability_set_node.node_id, "uses", 1.0))
        if need_node_id is not None:
            self.memory_graph.add_edge(MemoryEdge(need_node_id, idea_node.node_id, "inspires", idea.score))

        for capability in idea.capability_set.capabilities:
            capability_node = self.memory_graph.add_node(
                node_type="capability",
                content={
                    "capability_id": capability.id,
                    "description": capability.description,
                    "effectiveness": capability.effectiveness,
                    "cost": capability.cost,
                },
            )
            self.memory_graph.add_edge(MemoryEdge(idea_node.node_id, capability_node.node_id, "uses", capability.effectiveness))

    def _find_or_create_need_nodes(self, needs: list["AgentNeed"]) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for node in self.memory_graph.nodes.values():
            if node.node_type != "need":
                continue
            nid = node.content.get("need_id")
            if isinstance(nid, str):
                mapping[nid] = node.node_id

        for need in needs:
            if need.id in mapping:
                continue
            node = self.memory_graph.add_node(
                node_type="need",
                content={
                    "need_id": need.id,
                    "description": need.description,
                    "intensity": need.intensity,
                    "satisfaction": need.satisfaction,
                },
            )
            mapping[need.id] = node.node_id

        return mapping
