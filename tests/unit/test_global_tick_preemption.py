"""Phase 15: militocracy ``override_signal`` preempts execution order in GlobalTickCoordinator."""

from unittest.mock import MagicMock

from python.modules.nca.agent import NCAAgent
from python.modules.nca.coordination import GlobalTickCoordinator


def _agent(
    *,
    agent_id: str,
    discipline: float,
    idea: float,
    override_signal: bool,
) -> NCAAgent:
    agent = NCAAgent(world=MagicMock(), orientation=MagicMock())
    agent.agent_id = agent_id
    agent.synergy.collectivealignmentscore = 0.5
    agent.militocracy.discipline_score = discipline
    agent.militocracy.ideaqualityscore = idea
    agent.militocracy.militarydisciplinescore = discipline
    agent.militocracy.command_coherence = idea
    agent.militocracy.execution_priority = 0.9 if override_signal else 0.5
    agent.militocracy.override_signal = override_signal
    return agent


def test_override_signal_preempts_lower_scoring_agent() -> None:
    """Lower arbitration score but ``override_signal`` → runs before higher score without override."""
    coord = GlobalTickCoordinator()
    # Low score, must run first due to preemption
    slow = _agent(
        agent_id="a-preempt",
        discipline=0.1,
        idea=0.1,
        override_signal=True,
    )
    # Higher score, no preemption
    fast = _agent(
        agent_id="b-strong",
        discipline=0.95,
        idea=0.95,
        override_signal=False,
    )
    coord.register_agent(slow)
    coord.register_agent(fast)

    ordered = coord.compute_execution_order({"sharedgoalpressure": 0.5, "shared_goal_pressure": 0.5})
    assert [a.agent_id for a in ordered] == ["a-preempt", "b-strong"]


def test_without_override_order_follows_score_only() -> None:
    coord = GlobalTickCoordinator()
    low = _agent(agent_id="low", discipline=0.2, idea=0.2, override_signal=False)
    high = _agent(agent_id="high", discipline=0.9, idea=0.9, override_signal=False)
    coord.register_agent(low)
    coord.register_agent(high)
    ordered = coord.compute_execution_order({"sharedgoalpressure": 0.5})
    assert [a.agent_id for a in ordered] == ["high", "low"]
