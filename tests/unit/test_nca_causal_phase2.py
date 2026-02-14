from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "python") not in sys.path:
    sys.path.insert(0, str(ROOT / "python"))

from modules.nca.agent import NCAAgent
from modules.nca.causal import CausalGraph
from modules.nca.meta_observer import MetaObserver
from modules.nca.orientation import OrientationCenter
from modules.nca.world import GridWorld


def test_causal_graph_records_and_predicts() -> None:
    graph = CausalGraph(max_transitions=3)
    s0 = {"agent_position": 0, "goal_position": 4}
    s1 = {"agent_position": 1, "goal_position": 4}
    s2 = {"agent_position": 0, "goal_position": 4}

    graph.record_transition(s0, "right", s1)
    graph.record_transition(s1, "left", s2)

    assert graph.estimate_causal_effect("right") > 0
    assert graph.predict_outcome("left")["drift_probability"] >= 0
    assert graph.to_dict()["transition_count"] == 2


def test_agent_emits_causal_signals_and_tracks_context() -> None:
    world = GridWorld(
        size=12,
        start_position=0,
        goal_position=10,
        slippery_zone=(1, 2, 3),
        blocked_zone=(1,),
        reward_zone=(9, 10),
    )
    orientation = OrientationCenter(
        identity="phase2-test-agent",
        preferences={"progress": 0.8, "stability": 0.2},
        impulsiveness=0.3,
        stability_preference=0.6,
    )
    agent = NCAAgent(world=world, orientation=orientation)

    for _ in range(8):
        agent.step()

    assert len(agent.causal_graph.transitions) > 0
    assert isinstance(agent.signal_log, list)

    state = agent.build_state()
    assert "recent_transitions" in state.causal_context
    assert "causal_risk" in state.causal_context


def test_meta_observer_causal_fields_in_report() -> None:
    observer = MetaObserver(causal_alert_threshold=0.4)
    world = GridWorld(size=8, start_position=0, goal_position=7)
    orientation = OrientationCenter(identity="observer-test")
    agent = NCAAgent(world=world, orientation=orientation, meta_observer=observer)

    event = agent.step()
    report = event["analysis"]["report"]

    assert hasattr(report, "causal_risk")
    assert hasattr(report, "causal_score")
