from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Protocol

from ls.memory.edge import MemoryEdge
from ls.memory.memory_graph import MemoryGraph

if TYPE_CHECKING:
    from ls.cognition.need_market_engine import Capability, GoalContract


class NeedCategory(Enum):
    SURVIVAL = "survival"
    LEARNING = "learning"
    SOCIAL = "social"
    CREATIVE = "creative"
    NEUTRAL = "neutral"


@dataclass
class AgentNeed:
    id: str
    description: str
    intensity: float
    satisfaction: float
    category: NeedCategory = NeedCategory.NEUTRAL

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
    base_priority: float
    emotional_weight: float


@dataclass(frozen=True)
class EmotionalState:
    stress: float = 0.0

    def normalized_stress(self) -> float:
        return _clamp01(self.stress)


class EmotionRegulationEngine:
    def __init__(self, stress_up_per_failure: float = 0.12, stress_down_per_success: float = 0.05) -> None:
        self.stress_up_per_failure = stress_up_per_failure
        self.stress_down_per_success = stress_down_per_success

    def update(self, current: EmotionalState, outcomes: list[ActionOutcome]) -> EmotionalState:
        stress = current.normalized_stress()
        for outcome in outcomes:
            if outcome.success:
                stress -= self.stress_down_per_success * max(outcome.effect, 0.0)
            else:
                stress += self.stress_up_per_failure * max(outcome.effect, 0.2)
        return EmotionalState(stress=_clamp01(stress))


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
    """Need-driven loop with optional market matching for contract-driven goals."""

    def __init__(
        self,
        memory_graph: MemoryGraph,
        executor: ActionExecutor,
        regulation_engine: EmotionRegulationEngine | None = None,
        initial_emotional_state: EmotionalState | None = None,
    ):
        self.memory_graph = memory_graph
        self.executor = executor
        self.regulation_engine = regulation_engine or EmotionRegulationEngine()
        self.emotional_state = initial_emotional_state or EmotionalState()

    def run_cycle(
        self,
        needs: list[AgentNeed],
        max_goals: int = 3,
        capabilities: list["Capability"] | None = None,
        emotional_state: EmotionalState | None = None,
    ) -> list[ActionOutcome]:
        cycle_emotional_state = emotional_state or self.emotional_state

        for need in needs:
            need.decay()

        emotion_node_id = self._record_emotional_state(cycle_emotional_state)

        goals, contracts = self.generate_goals(
            needs,
            max_goals=max_goals,
            capabilities=capabilities,
            emotional_state=cycle_emotional_state,
        )
        outcomes: list[ActionOutcome] = []

        for goal in goals:
            strategy, strategy_node_id, need_node_ids = self._prepare_strategy_and_links(
                goal,
                contracts.get(goal.id),
                emotion_node_id,
            )

            for step in strategy.steps:
                outcome, action_node_id = self._execute_step(goal, strategy_node_id, step)
                outcomes.append(outcome)

                outcome_node = self.memory_graph.add_node(
                    node_type="outcome",
                    content={"goal_id": goal.id, "success": outcome.success, "effect": outcome.effect, "details": outcome.details},
                )
                self.memory_graph.add_edge(MemoryEdge(action_node_id, outcome_node.node_id, "leads_to", 1.0))
                self.reflect(outcome, goal, need_node_ids, outcome_node.node_id)

        self.emotional_state = self.regulation_engine.update(cycle_emotional_state, outcomes)
        return outcomes

    def generate_goals(
        self,
        needs: list[AgentNeed],
        max_goals: int = 3,
        capabilities: list["Capability"] | None = None,
        emotional_state: EmotionalState | None = None,
    ) -> tuple[list[AgentGoal], dict[str, "GoalContract"]]:
        stress = emotional_state.normalized_stress() if emotional_state else self.emotional_state.normalized_stress()

        if capabilities:
            from ls.cognition.need_market_engine import NeedMarketEngine

            market = NeedMarketEngine(self.memory_graph)
            contracts = market.match(needs, capabilities, max_contracts=max_goals)
            goals: list[AgentGoal] = []
            contract_map: dict[str, GoalContract] = {}
            needs_index = {need.id: need for need in needs}

            for contract in contracts:
                need = needs_index.get(contract.need_id)
                if need is None:
                    continue
                emotional_weight = self._stress_weight_for_need(need, stress)
                priority = self._effective_contract_priority(need, contract.expected_effect, contract.cost, emotional_weight)
                goal = AgentGoal(
                    id=f"goal-{contract.id}",
                    description=f"Contract {contract.id} for need '{need.description}'",
                    linked_needs=[need],
                    priority=priority,
                    base_priority=contract.priority,
                    emotional_weight=emotional_weight,
                )
                goals.append(goal)
                contract_map[goal.id] = contract

            return goals, contract_map

        ranked = sorted(needs, key=lambda n: self._effective_priority(n, stress), reverse=True)
        goals = [
            AgentGoal(
                id=f"goal-{need.id}",
                description=f"Improve need '{need.description}'",
                linked_needs=[need],
                priority=self._effective_priority(need, stress),
                base_priority=need.intensity * (1.0 - need.satisfaction),
                emotional_weight=self._stress_weight_for_need(need, stress),
            )
            for need in ranked[:max_goals]
        ]
        return goals, {}

    @staticmethod
    def _effective_contract_priority(
        need: AgentNeed,
        expected_effect: float,
        cost: float,
        emotional_weight: float,
    ) -> float:
        adjusted_effect = expected_effect * emotional_weight
        return (need.intensity * adjusted_effect) - cost

    @staticmethod
    def _effective_priority(need: AgentNeed, stress: float) -> float:
        base_priority = need.intensity * (1.0 - need.satisfaction)
        return base_priority * MotivationEngine._stress_weight_for_need(need, stress)

    @staticmethod
    def _infer_category(need: AgentNeed) -> NeedCategory:
        signature = f"{need.id.lower()} {need.description.lower()}"
        if any(key in signature for key in {"safety", "risk", "threat", "energy", "rest", "secure"}):
            return NeedCategory.SURVIVAL
        if any(key in signature for key in {"learning", "curiosity", "exploration"}):
            return NeedCategory.LEARNING
        if "social" in signature:
            return NeedCategory.SOCIAL
        if any(key in signature for key in {"creative", "creativity", "ideation"}):
            return NeedCategory.CREATIVE
        return NeedCategory.NEUTRAL

    @staticmethod
    def _stress_weight_for_need(need: AgentNeed, stress: float) -> float:
        category = need.category if need.category != NeedCategory.NEUTRAL else MotivationEngine._infer_category(need)
        if category == NeedCategory.SURVIVAL:
            return 1.0 + (0.8 * stress)
        if category in {NeedCategory.LEARNING, NeedCategory.SOCIAL, NeedCategory.CREATIVE}:
            return 1.0 - (0.5 * stress)
        return 1.0

    @staticmethod
    def build_strategy(goal: AgentGoal) -> Strategy:
        """Baseline fallback strategy; TODO: replace with richer planning policy."""
        return Strategy(goal=goal, steps=[f"assess:{goal.id}", f"execute:{goal.id}", f"verify:{goal.id}"])

    def reflect(self, outcome: ActionOutcome, goal: AgentGoal, need_node_ids: list[str], outcome_node_id: str) -> None:
        for need in goal.linked_needs:
            if outcome.success:
                need.satisfy(max(outcome.effect, 0.0))
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

            for node_id in need_node_ids:
                node = self.memory_graph.get_node(node_id)
                if node and node.content.get("need_id") == need.id:
                    self.memory_graph.add_edge(MemoryEdge(reflection_node.node_id, node_id, "updates", 1.0))

    def _prepare_strategy_and_links(
        self,
        goal: AgentGoal,
        contract: "GoalContract" | None,
        emotion_node_id: str,
    ) -> tuple[Strategy, str, list[str]]:
        if contract is not None:
            from ls.cognition.need_market_engine import NeedMarketEngine

            strategy = NeedMarketEngine.build_strategy(contract, goal)
            strategy_node = self.memory_graph.add_node(
                node_type="strategy",
                content={"goal_id": goal.id, "contract_id": contract.id, "steps": strategy.steps},
            )
            contract_node_id = contract.contract_node_id
            if contract_node_id and self.memory_graph.get_node(contract_node_id):
                self.memory_graph.add_edge(MemoryEdge(contract_node_id, strategy_node.node_id, "produces", contract.priority))
            else:
                fallback_contract = self.memory_graph.add_node(
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
                self.memory_graph.add_edge(MemoryEdge(fallback_contract.node_id, strategy_node.node_id, "produces", contract.priority))
            self.memory_graph.add_edge(MemoryEdge(emotion_node_id, strategy_node.node_id, "modulates", 1.0))
            return strategy, strategy_node.node_id, self._find_need_nodes(goal)

        strategy = self.build_strategy(goal)
        need_node_ids, goal_node_id = self._link_need_to_goal(goal, emotion_node_id)
        strategy_node = self.memory_graph.add_node(node_type="strategy", content={"goal_id": goal.id, "steps": strategy.steps})
        self.memory_graph.add_edge(MemoryEdge(goal_node_id, strategy_node.node_id, "produces", goal.priority))
        return strategy, strategy_node.node_id, need_node_ids

    def _record_emotional_state(self, emotional_state: EmotionalState) -> str:
        emotion_node = self.memory_graph.add_node(
            node_type="emotional_state",
            content={
                "stress": emotional_state.normalized_stress(),
            },
        )
        return emotion_node.node_id

    def _execute_step(self, goal: AgentGoal, strategy_node_id: str, step: str) -> tuple[ActionOutcome, str]:
        action_node = self.memory_graph.add_node(node_type="action", content={"goal_id": goal.id, "step": step})
        self.memory_graph.add_edge(MemoryEdge(strategy_node_id, action_node.node_id, "executes", 1.0))
        return self.executor.execute(step, goal), action_node.node_id

    def _link_need_to_goal(self, goal: AgentGoal, emotion_node_id: str) -> tuple[list[str], str]:
        need_node_ids: list[str] = []
        goal_node = self.memory_graph.add_node(
            node_type="goal",
            content={
                "goal_id": goal.id,
                "description": goal.description,
                "priority": goal.priority,
                "base_priority": goal.base_priority,
                "emotional_weight": goal.emotional_weight,
            },
        )
        self.memory_graph.add_edge(MemoryEdge(emotion_node_id, goal_node.node_id, "influences", goal.emotional_weight))

        for need in goal.linked_needs:
            existing_need = self.memory_graph.find_first_node(node_type="need", content_key="need_id", content_value=need.id)
            need_node = existing_need or self.memory_graph.add_node(
                node_type="need",
                content={
                    "need_id": need.id,
                    "description": need.description,
                    "intensity": need.intensity,
                    "satisfaction": need.satisfaction,
                    "category": need.category.value,
                },
            )
            need_node_ids.append(need_node.node_id)
            self.memory_graph.add_edge(MemoryEdge(need_node.node_id, goal_node.node_id, "generates", goal.priority))

        return need_node_ids, goal_node.node_id

    def _find_need_nodes(self, goal: AgentGoal) -> list[str]:
        return [
            node.node_id
            for need in goal.linked_needs
            for node in self.memory_graph.find_nodes(node_type="need", content_key="need_id", content_value=need.id)
        ]


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))
