from __future__ import annotations

# ruff: noqa: E402

import sys
import threading
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


def test_execution_order_changes_with_scores() -> None:
    system = MultiAgentSystem()
    low = _agent("a-low")
    high = _agent("b-high")

    low.militocracy.discipline_score = 0.1
    low.militocracy.ideaqualityscore = 0.1
    low.synergy.collectivealignmentscore = 0.1

    high.militocracy.discipline_score = 0.9
    high.militocracy.ideaqualityscore = 0.9
    high.synergy.collectivealignmentscore = 0.9

    system.add_agent(low)
    system.add_agent(high)

    order = system.coordinator.prepare_tick(system.collective_state()).execution_order
    assert order[0] == "b-high"


def test_execution_order_tie_breaks_by_agent_id() -> None:
    system = MultiAgentSystem()
    for agent_id in ("z-agent", "a-agent"):
        agent = _agent(agent_id)
        agent.militocracy.discipline_score = 0.5
        agent.militocracy.ideaqualityscore = 0.5
        agent.synergy.collectivealignmentscore = 0.5
        system.add_agent(agent)

    order = system.coordinator.prepare_tick(system.collective_state()).execution_order
    assert order == ["a-agent", "z-agent"]


def test_collective_state_includes_phase14_aggregates() -> None:
    system = MultiAgentSystem()
    for idx in range(3):
        system.add_agent(_agent(f"x-{idx}", start=idx))

    _ = system.step_all()
    state = system.collective_state()

    assert "sharedgoalpressure" in state
    assert "execution_order" in state
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


def test_deterministic_signal_bus_local_and_group() -> None:
    bus = DeterministicSignalBus()
    received: list[str] = []

    bus.subscribe_agent("a1", lambda s: received.append(f"agent:{s.signal_type}"))
    bus.subscribe_group("g1", lambda s: received.append(f"group:{s.signal_type}"))

    bus.emit_local(InternalSignal(signal_type="local"), target_agent_id="a1")
    bus.emit_group(InternalSignal(signal_type="group"), group_id="g1")
    out = bus.process_tick()

    assert [s.signal_type for s in out] == ["local", "group"]
    assert "agent:local" in received
    assert "group:group" in received


def test_deterministic_signal_bus_has_tick_guard() -> None:
    bus = DeterministicSignalBus(max_signals_per_tick=3)

    def handler(signal: InternalSignal) -> None:
        if signal.signal_type.startswith("loop"):
            bus.emit(InternalSignal(signal_type=f"loop-{len(signal.signal_type)}"))

    bus.subscribe(handler)
    bus.emit(InternalSignal(signal_type="loop"))
    processed = bus.process_tick()

    assert len(processed) == 3


def test_step_all_uses_coordinator_order() -> None:
    system = MultiAgentSystem()
    seen: list[str] = []

    first = _agent("first")
    second = _agent("second")

    first.militocracy.discipline_score = 0.1
    first.militocracy.ideaqualityscore = 0.1
    first.synergy.collectivealignmentscore = 0.1

    second.militocracy.discipline_score = 0.9
    second.militocracy.ideaqualityscore = 0.9
    second.synergy.collectivealignmentscore = 0.9

    def _wrap(agent: NCAAgent) -> None:
        original = agent.step

        def _tracked_step() -> dict[str, object]:
            seen.append(getattr(agent, "agent_id", "unknown"))
            return original()

        agent.step = _tracked_step  # type: ignore[assignment]

    _wrap(first)
    _wrap(second)

    system.add_agent(first)
    system.add_agent(second)

    system.step_all()

    assert seen[0] == "second"


def test_multi_agent_system_uses_deterministic_signal_bus() -> None:
    system = MultiAgentSystem()
    assert isinstance(system.collective_signal_bus, DeterministicSignalBus)

    system.add_agent(_agent("a0"))
    system.add_agent(_agent("a1"))
    system.step_all()

    # process_tick is called inside step_all, so pending queue must be empty here
    assert system.collective_signal_bus.process_tick() == []


def test_deterministic_signal_bus_thread_safety() -> None:
    bus = DeterministicSignalBus()
    received: list[str] = []
    recv_lock = threading.Lock()

    def handler(signal: InternalSignal) -> None:
        with recv_lock:
            received.append(signal.signal_type)

    bus.subscribe(handler)

    def emitter(idx: int) -> None:
        for i in range(100):
            bus.emit(InternalSignal(signal_type=f"t{idx}-{i}"))

    threads = [threading.Thread(target=emitter, args=(idx,)) for idx in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    processed = bus.process_tick()
    assert len(processed) == 500
    assert len(received) == 500


def test_execution_order_stability_with_equal_scores() -> None:
    system = MultiAgentSystem()
    for idx in range(5):
        agent = _agent(f"agent-{idx}")
        agent.militocracy.discipline_score = 0.5
        agent.militocracy.ideaqualityscore = 0.5
        agent.synergy.collectivealignmentscore = 0.5
        system.add_agent(agent)

    orders = [
        system.coordinator.prepare_tick(system.collective_state()).execution_order
        for _ in range(10)
    ]

    assert all(order == orders[0] for order in orders)
