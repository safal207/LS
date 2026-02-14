from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.nca.agent import NCAAgent
from modules.nca.meta_observer import MetaObserver
from modules.nca.multiagent import MultiAgentSystem
from modules.nca.orientation import OrientationCenter
from modules.nca.world import GridWorld


def run_demo(steps: int = 6, agents_count: int = 2) -> dict[str, object]:
    system = MultiAgentSystem()

    for idx in range(max(1, min(2, agents_count))):
        world = GridWorld(size=10, start_position=idx, goal_position=9)
        orientation = OrientationCenter(
            identity=f"self-model-agent-{idx}",
            preferences={"progress": 0.9, "stability": 0.25},
            impulsiveness=0.3,
            stability_preference=0.75,
        )
        system.add_agent(NCAAgent(world=world, orientation=orientation, meta_observer=MetaObserver()))

    events: list[dict[str, object]] = []
    for _ in range(steps):
        events.extend(system.step_all())

    collective = system.collective_state()
    print("=== NCA Self-Modeling Demo ===")
    for agent in system.agents:
        model = agent.self_model.to_dict()
        predicted = model.get("predicted_state", {})
        print(f"agent={agent.orientation.identity}")
        print("  identity graph nodes:", len(model.get("identity_graph", {}).get("nodes", [])))
        print("  identity graph edges:", len(model.get("identity_graph", {}).get("edges", [])))
        print("  self-model drift:", model.get("identity_drift_score", 0.0))
        print("  predicted future state:", predicted)
        print(
            "  self-alignment corrections:",
            {
                "impulsiveness": agent.orientation.impulsiveness,
                "stability_preference": agent.orientation.stability_preference,
                "invariants": agent.orientation.invariants,
            },
        )

    print("collective self-alignment:", collective.get("collective_self_alignment"))
    return {"events": events, "collective": collective}


if __name__ == "__main__":
    run_demo()
