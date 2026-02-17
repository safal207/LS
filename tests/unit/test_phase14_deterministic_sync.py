from __future__ import annotations

# ruff: noqa: E402

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "python") not in sys.path:
    sys.path.insert(0, str(ROOT / "python"))

from modules.nca.agent import NCAAgent
from modules.nca.multiagent import MultiAgentSystem
from modules.nca.orientation import OrientationCenter
from modules.nca.signals import DeterministicSignalBus, InternalSignal
from modules.nca.world import GridWorld


def _agent(agent_id: str, start: int = 0) -> NCAAgent:
    return NCAAgent(world=GridWorld(size=10, start_position=start, goal_position=9), orientation=OrientationCenter(identity=agent_id))


def test_execution_order_is_deterministic() -> None:
    system = MultiAgentSystem()
    for idx in range(3):
        agent = _agent(f"agent-{idx}", start=idx)
        agent.militocracy.discipline_score = 0.7
        agent.militocracy.ideaqualityscore = 0.6
        agent.synergy.collectivealignmentscore = 0.8
        system.add_agent(agent)

    before = system.coordinator.tick(system.collective_state()).execution_order
    after = system.coordinator.tick(system.collective_state()).execution_order

    assert before == after


def test_collective_state_includes_phase14_aggregates() -> None:
    system = MultiAgentSystem()
    for idx in range(3):
        system.add_agent(_agent(f"x-{idx}", start=idx))

    state = system.collective_state()

    assert "sharedgoalpressure" in state
    assert 0.0 <= state["sharedgoalpressure"] <= 1.0


def test_deterministic_signal_bus_no_reentrancy_loss() -> None:
    bus = DeterministicSignalBus()
    received: list[str] = []

    def handler(signal: InternalSignal) -> None:
        received.append(signal.signal_type)
        if signal.signal_type == "one":
            bus.emit(InternalSignal(signal_type="two"))

    bus.subscribe(handler)
    bus.emit(InternalSignal(signal_type="one"))
    processed = bus.process_tick()

    assert [s.signal_type for s in processed] == ["one", "two"]
    assert received == ["one", "two"]
