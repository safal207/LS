from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "python") not in sys.path:
    sys.path.insert(0, str(ROOT / "python"))

from modules.nca.agent import NCAAgent
from modules.nca.meta_observer import MetaObserver
from modules.nca.multiagent import MultiAgentSystem
from modules.nca.orientation import OrientationCenter
from modules.nca.shared_causal import SharedCausalGraph
from modules.nca.signals import CollectiveSignalBus, InternalSignal
from modules.nca.trajectories import TrajectoryOption, TrajectoryPlanner
from modules.nca.world import GridWorld


def test_shared_causal_graph_merge_and_predict() -> None:
    world = GridWorld(size=8, start_position=0, goal_position=7)
    agent = NCAAgent(world=world, orientation=OrientationCenter(identity="a0"))
    for _ in range(4):
        agent.step()

    shared = SharedCausalGraph(max_transitions=500)
    shared.merge(agent.causal_graph, agent_id="a0")

    outcome = shared.predict_collective_outcome("right")
    assert "collective_effect" in outcome
    assert "collective_drift" in outcome
    assert "agent_contributions" in outcome


def test_collective_signal_bus_scopes() -> None:
    bus = CollectiveSignalBus()
    received: list[str] = []

    bus.subscribe_agent("a1", lambda s: received.append(f"agent:{s.signal_type}"))
    bus.subscribe_group("g", lambda s: received.append(f"group:{s.signal_type}"))

    bus.emit_local(InternalSignal(signal_type="local", payload={"sourceagentid": "a0"}), target_agent_id="a1")
    bus.emit_group(InternalSignal(signal_type="group", payload={"sourceagentid": "a0"}), group_id="g")
    bus.emit_broadcast(InternalSignal(signal_type="broadcast", payload={"sourceagentid": "a0"}))

    assert any(item.startswith("agent:") for item in received)
    assert any(item.startswith("group:") for item in received)


def test_multi_agent_system_runs_collective_steps() -> None:
    system = MultiAgentSystem()
    for idx in range(3):
        world = GridWorld(size=10, start_position=idx, goal_position=9)
        orientation = OrientationCenter(identity=f"agent-{idx}")
        system.add_agent(NCAAgent(world=world, orientation=orientation))

    events = system.step_all()
    collective = system.collective_state()

    assert len(events) == 3
    assert "shared_causal" in collective
    assert "agent_positions" in collective


def test_trajectory_collective_score_and_meta_report_fields() -> None:
    world = GridWorld(size=10, start_position=1, goal_position=9)
    orientation = OrientationCenter(identity="planner-agent")
    agent = NCAAgent(world=world, orientation=orientation, meta_observer=MetaObserver())
    state = agent.build_state()

    planner = TrajectoryPlanner(causal_graph=agent.causal_graph)
    option = TrajectoryOption(action="right", score=0.0, details={"projected_position": 2})
    collective_state = {
        "agent_positions": {"x": 2},
        "shared_causal": {"by_action": {"right": {"collective_effect": 0.4, "collective_drift": 0.1}}},
    }

    collective_score = planner.evaluatecollectivescore(option, state, collective_state)
    assert isinstance(collective_score, float)

    event = agent.step()
    report = event["analysis"]["report"]
    assert hasattr(report, "collective_score")
    assert hasattr(report, "collective_risk")
    assert hasattr(report, "collective_alignment")
