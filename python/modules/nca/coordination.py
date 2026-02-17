from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .agent import NCAAgent


@dataclass
class MultiAgentContext:
    """Shared deterministic context for a single global tick."""

    collective_alignment: float
    collectivemetadrift: float
    collectiveidentityshift: bool
    sharedgoalpressure: float
    discipline_vector: dict[str, float] = field(default_factory=dict)
    execution_order: list[str] = field(default_factory=list)
    aggregated_signals: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SynergyMilitocracyArbitrationLayer:
    """Computes deterministic execution scores from synergy + militocracy signals."""

    w_s: float = 0.4
    w_m: float = 0.3
    w_i: float = 0.2
    w_g: float = 0.1  # Keep in sync with docs/PHASE14_OVERVIEW.md

    def score(self, agent: NCAAgent, collective_state: dict[str, Any]) -> float:
        synergy = getattr(agent, "synergy", None)
        militocracy = getattr(agent, "militocracy", None)

        collective_alignment = float(getattr(synergy, "collectivealignmentscore", 0.5))
        discipline = float(getattr(militocracy, "discipline_score", getattr(militocracy, "militarydisciplinescore", 0.5)))
        idea_quality = float(getattr(militocracy, "ideaqualityscore", 0.5))
        shared_goal_pressure = float(collective_state.get("sharedgoalpressure", collective_state.get("collective_goal_pressure", 0.5)))

        base_score = (
            self.w_s * collective_alignment
            + self.w_m * discipline
            + self.w_i * idea_quality
            + self.w_g * shared_goal_pressure
        )
        # Phase 14: override_signal is an explicit command escalation hint from MilitocracyEngine.
        override = bool(getattr(militocracy, "override_signal", False))
        return min(1.0, base_score + (0.05 if override else 0.0))


@dataclass
class GlobalTickCoordinator:
    """Deterministic global update coordinator for multi-agent ticks."""

    arbitration: SynergyMilitocracyArbitrationLayer = field(default_factory=SynergyMilitocracyArbitrationLayer)
    agents: list[NCAAgent] = field(default_factory=list)

    def register_agent(self, agent: NCAAgent) -> None:
        if agent not in self.agents:
            self.agents.append(agent)

    def compute_execution_order(self, collective_state: dict[str, Any]) -> list[NCAAgent]:
        scored: list[tuple[float, str, NCAAgent]] = []
        for idx, agent in enumerate(self.agents):
            agent_id = str(getattr(agent, "agent_id", f"agent-{idx}"))
            score = self.arbitration.score(agent, collective_state)
            scored.append((score, agent_id, agent))

        scored.sort(key=lambda item: (-item[0], item[1]))
        return [item[2] for item in scored]

    def prepare_tick(self, collective_state: dict[str, Any], aggregated_signals: list[dict[str, Any]] | None = None) -> MultiAgentContext:
        """Prepare deterministic context for the next global tick (without executing agents)."""
        ordered_agents = self.compute_execution_order(collective_state)
        ordered_ids = [str(getattr(agent, "agent_id", "unknown")) for agent in ordered_agents]

        discipline_vector = {
            str(getattr(agent, "agent_id", "unknown")): float(
                getattr(getattr(agent, "militocracy", None), "discipline_score", 0.5)
            )
            for agent in self.agents
        }

        return MultiAgentContext(
            collective_alignment=float(collective_state.get("collectivemetaalignment", 0.5)),
            collectivemetadrift=float(collective_state.get("collectivemetadrift", 0.0)),
            collectiveidentityshift=bool(collective_state.get("collectiveidentityshift", False)),
            sharedgoalpressure=float(collective_state.get("sharedgoalpressure", collective_state.get("collective_goal_pressure", 0.5))),
            discipline_vector=discipline_vector,
            execution_order=ordered_ids,
            aggregated_signals=list(aggregated_signals or []),
        )


    def tick(self, collective_state: dict[str, Any], aggregated_signals: list[dict[str, Any]] | None = None) -> MultiAgentContext:
        """Backward-compatible alias for prepare_tick()."""
        return self.prepare_tick(collective_state, aggregated_signals=aggregated_signals)
