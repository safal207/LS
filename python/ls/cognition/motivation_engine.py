from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ls.memory.edge import MemoryEdge
from ls.memory.memory_graph import MemoryGraph


@dataclass
class AgentNeed:
    id: str
    description: str
    intensity: float
    satisfaction: float

    def update_intensity(self, delta: float) -> None:
        self.intensity = _clamp01(self.intensity + delta)

    def satisfy(self, amount: float) -> None:
        self.satisfaction = _clamp01(self.satisfaction + amount)
        self.intensity = _clamp01(self.intensity - amount)

    def decay(self, factor: float = 0.05) -> None:
        self.satisfaction = _clamp01(self.satisfaction - factor)
        self.intensity = _clamp01(self.intensity + factor)


@dataclass
class AgentGoal:
    id: str
    description: str
    linked_needs: list[AgentNeed]
    priority: float


@dataclass
class Strategy:
    goal: AgentGoal
    steps: list[str]


@dataclass(frozen=True)
class ActionOutcome:
    success: bool
    effect: float
    details: str = ""


class ActionExecutor(Protocol):
    def execute(self, step: str, goal: AgentGoal) -> ActionOutcome:
        ...


class MotivationEngine:
    """Need-driven loop: needs -> goals -> strategy -> action -> reflection -> memory."""

    def __init__(self, memory_graph: MemoryGraph, executor: ActionExecutor):
        self.memory_graph = memory_graph
        self.executor = executor

    def run_cycle(self, needs: list[AgentNeed], max_goals: int = 3) -> list[ActionOutcome]:
        for need in needs:
            need.decay()

        goals = self.generate_goals(needs, max_goals=max_goals)
        outcomes: list[ActionOutcome] = []

        for goal in goals:
            strategy = self.build_strategy(goal)
            need_node_ids, goal_node_id = self._link_need_to_goal(goal)
            strategy_node = self.memory_graph.add_node(
                node_type="strategy",
                content={"goal_id": goal.id, "steps": strategy.steps},
            )

            self.memory_graph.add_edge(MemoryEdge(goal_node_id, strategy_node.node_id, "produces", goal.priority))

            for step in strategy.steps:
                action_node = self.memory_graph.add_node(node_type="action", content={"goal_id": goal.id, "step": step})
                self.memory_graph.add_edge(MemoryEdge(strategy_node.node_id, action_node.node_id, "executes", 1.0))

                outcome = self.executor.execute(step, goal)
                outcomes.append(outcome)

                outcome_node = self.memory_graph.add_node(
                    node_type="outcome",
                    content={"goal_id": goal.id, "success": outcome.success, "effect": outcome.effect, "details": outcome.details},
                )
                self.memory_graph.add_edge(MemoryEdge(action_node.node_id, outcome_node.node_id, "leads_to", 1.0))

                self.reflect(outcome, goal, need_node_ids, outcome_node.node_id)

        return outcomes

    def generate_goals(self, needs: list[AgentNeed], max_goals: int = 3) -> list[AgentGoal]:
        ranked = sorted(needs, key=lambda n: n.intensity * (1.0 - n.satisfaction), reverse=True)
        goals: list[AgentGoal] = []

        for need in ranked[:max_goals]:
            priority = need.intensity * (1.0 - need.satisfaction)
            goals.append(
                AgentGoal(
                    id=f"goal-{need.id}",
                    description=f"Improve need '{need.description}'",
                    linked_needs=[need],
                    priority=priority,
                )
            )

        return goals

    @staticmethod
    def build_strategy(goal: AgentGoal) -> Strategy:
        steps = [
            f"assess:{goal.id}",
            f"execute:{goal.id}",
            f"verify:{goal.id}",
        ]
        return Strategy(goal=goal, steps=steps)

    def reflect(self, outcome: ActionOutcome, goal: AgentGoal, need_node_ids: list[str], outcome_node_id: str) -> None:
        for need in goal.linked_needs:
            if outcome.success:
                delta = max(outcome.effect, 0.0)
                need.satisfy(delta)
            else:
                need.update_intensity(max(outcome.effect, 0.0))

            reflection_node = self.memory_graph.add_node(
                node_type="reflection",
                content={
                    "goal_id": goal.id,
                    "need_id": need.id,
                    "success": outcome.success,
                    "intensity": need.intensity,
                    "satisfaction": need.satisfaction,
                },
            )
            self.memory_graph.add_edge(MemoryEdge(outcome_node_id, reflection_node.node_id, "updates", 1.0))

            need_node_id = f"need-{need.id}"
            if need_node_id in need_node_ids:
                self.memory_graph.add_edge(MemoryEdge(reflection_node.node_id, need_node_id, "updates", 1.0))

    def _link_need_to_goal(self, goal: AgentGoal) -> tuple[list[str], str]:
        need_node_ids: list[str] = []

        goal_node = self.memory_graph.add_node(
            node_type="goal",
            content={"goal_id": goal.id, "description": goal.description, "priority": goal.priority},
        )

        for need in goal.linked_needs:
            need_node = self.memory_graph.add_node(
                node_type="need",
                content={
                    "need_id": need.id,
                    "description": need.description,
                    "intensity": need.intensity,
                    "satisfaction": need.satisfaction,
                },
            )
            need_node_ids.append(need_node.node_id)
            self.memory_graph.add_edge(MemoryEdge(need_node.node_id, goal_node.node_id, "generates", goal.priority))

        return need_node_ids, goal_node.node_id


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))
