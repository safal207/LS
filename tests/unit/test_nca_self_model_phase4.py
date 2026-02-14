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
from modules.nca.self_model import SelfModel
from modules.nca.trajectories import TrajectoryOption
from modules.nca.world import GridWorld


def test_self_model_builds_identity_graph_and_prediction() -> None:
    model = SelfModel(max_history=100)
    for idx in range(5):
        model.updatefromstate(
            {
                "t": idx,
                "preferences": {"progress": 0.7 + (idx * 0.01), "stability": 0.2},
                "personality": {"impulsiveness": 0.3, "stability_preference": 0.8, "risk_tolerance": 0.4},
            }
        )

    payload = model.to_dict()
    assert len(payload["identity_graph"]["nodes"]) == 5
    assert len(payload["identity_graph"]["edges"]) == 4
    assert "predictedselfconsistency" in payload["predicted_state"]
    assert "cognitive_patterns" in payload
    assert "bias_history" in payload


def test_agent_event_contains_self_model_and_meta_fields() -> None:
    world = GridWorld(size=10, start_position=0, goal_position=9)
    orientation = OrientationCenter(identity="phase4-agent", preferences={"progress": 0.8, "stability": 0.3})
    agent = NCAAgent(world=world, orientation=orientation, meta_observer=MetaObserver())

    event = agent.step()
    assert "self_model" in event
    assert "identity_graph" in event["self_model"]
    assert "metacognition" in event

    report = event["analysis"]["report"]
    assert hasattr(report, "self_model_snapshot")
    assert hasattr(report, "identity_drift_score")
    assert hasattr(report, "predicted_self_consistency")
    assert hasattr(report, "meta_consistency")
    assert hasattr(report, "observerbiasscore")
    assert hasattr(report, "meta_drift")


def test_self_alignment_score_is_applied_to_trajectory_details() -> None:
    world = GridWorld(size=10, start_position=1, goal_position=9)
    orientation = OrientationCenter(identity="align-agent")
    agent = NCAAgent(world=world, orientation=orientation)

    state = agent.build_state()
    agent.self_model.update_from_state(state)
    options = [TrajectoryOption(action="right", score=0.0, details={"projected_position": 2})]
    evaluated = agent.planner.evaluate(options, state, collective_state={}, self_model=agent.self_model)

    assert "self_alignment_score" in evaluated[0].details


def test_multi_agent_collective_self_alignment_fields() -> None:
    system = MultiAgentSystem()
    for idx in range(2):
        world = GridWorld(size=8, start_position=idx, goal_position=7)
        orientation = OrientationCenter(identity=f"sm-{idx}")
        system.add_agent(NCAAgent(world=world, orientation=orientation), agent_id=f"sm-{idx}")

    system.step_all()
    collective = system.collective_state()

    assert "self_models" in collective
    assert "collective_self_alignment" in collective
    assert "collectiveidentityshift" in collective
    assert "collectivemetaalignment" in collective
    assert "collectivemetadrift" in collective
    assert "collectivemetastabilization" in collective


def test_meta_alignment_score_is_applied_to_trajectory_details() -> None:
    world = GridWorld(size=10, start_position=1, goal_position=9)
    orientation = OrientationCenter(identity="meta-align-agent")
    agent = NCAAgent(world=world, orientation=orientation)

    state = agent.build_state()
    agent.self_model.update_from_state(state)
    options = [TrajectoryOption(action="right", score=0.0, details={"projected_position": 2})]
    evaluated = agent.planner.evaluate(
        options,
        state,
        collective_state={},
        self_model=agent.self_model,
        metafeedback={"meta_drift": 0.5, "biases": ["oscillation_bias"], "orientation_corrections": {"observerbiasscore": 0.2}},
    )

    assert "meta_alignment_score" in evaluated[0].details
