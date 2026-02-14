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


def run_demo(steps: int = 10, agents_count: int = 3) -> dict[str, object]:
    system = MultiAgentSystem()
    for idx in range(max(1, agents_count)):
        world = GridWorld(size=12, start_position=idx, goal_position=11, noise_level=0.25 + (0.05 * idx))
        orientation = OrientationCenter(
            identity=f"meta-agent-{idx}",
            preferences={"progress": 0.85, "stability": 0.3},
            impulsiveness=0.34,
            stability_preference=0.72,
        )
        system.add_agent(NCAAgent(world=world, orientation=orientation, meta_observer=MetaObserver()), agent_id=f"meta-{idx}")

    events: list[dict[str, object]] = []
    for _ in range(steps):
        events.extend(system.step_all())

    collective = system.collective_state()
    print("=== NCA Meta-Cognition Demo ===")
    for agent in system.agents:
        event = next((e for e in reversed(events) if e.get("agent_id") == getattr(agent, "agent_id", "")), {})
        feedback = event.get("metacognition", {}) if isinstance(event, dict) else {}
        model = agent.self_model.to_dict()
        print(f"agent={agent.agent_id}")
        print("  meta-drift:", feedback.get("meta_drift", 0.0))
        print("  cognitive biases:", feedback.get("biases", []))
        print("  corrections applied:", agent.metacognition.suggest_corrections())
        print("  stability over time:", 1.0 - float(model.get("meta_drift_score", 0.0)))

    print("collective meta-alignment:", collective.get("collectivemetaalignment", 1.0))
    print("collective meta-drift:", collective.get("collectivemetadrift", 0.0))
    return {"events": events, "collective": collective}


if __name__ == "__main__":
    run_demo()
