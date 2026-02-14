from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "python") not in sys.path:
    sys.path.insert(0, str(ROOT / "python"))

from modules.nca.agent import NCAAgent
from modules.nca.multiagent import MultiAgentSystem
from modules.nca.orientation import OrientationCenter
from modules.nca.trajectories import TrajectoryOption
from modules.nca.world import GridWorld


def test_agent_step_includes_identity_core_and_initiative() -> None:
    world = GridWorld(size=10, start_position=0, goal_position=9)
    orientation = OrientationCenter(identity="phase6-agent", preferences={"progress": 0.8, "stability": 0.3})
    agent = NCAAgent(world=world, orientation=orientation)

    event = agent.step()

    assert "identity_core" in event
    assert "initiative" in event
    assert "agency_level" in event["identity_core"]
    assert "identity_integrity" in event["identity_core"]


def test_planner_applies_initiative_score() -> None:
    world = GridWorld(size=10, start_position=0, goal_position=9)
    orientation = OrientationCenter(identity="planner-initiative")
    agent = NCAAgent(world=world, orientation=orientation)

    state = agent.build_state()
    options = [TrajectoryOption(action="forward", score=0.0, details={"projected_position": 1})]
    evaluated = agent.planner.evaluate(
        options,
        state,
        self_model=agent.self_model,
        metafeedback={"meta_drift": 0.1},
        initiative={"mode": "explore", "preferred_actions": ["forward"], "agency_level": 0.7, "identity_integrity": 0.8},
    )

    assert "initiative_score" in evaluated[0].details
    assert evaluated[0].details["initiative_score"] > 0.0


def test_collective_agency_metrics_available() -> None:
    system = MultiAgentSystem()
    for idx in range(2):
        world = GridWorld(size=8, start_position=idx, goal_position=7)
        orientation = OrientationCenter(identity=f"phase6-{idx}")
        system.add_agent(NCAAgent(world=world, orientation=orientation), agent_id=f"phase6-{idx}")

    system.step_all()
    collective = system.collective_state()

    assert "collectiveagencylevel" in collective
    assert "collectiveidentityintegrity" in collective
    assert "collective_initiative" in collective
