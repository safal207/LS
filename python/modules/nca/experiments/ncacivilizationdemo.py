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


def run_demo(steps: int = 8) -> dict[str, object]:
    system = MultiAgentSystem()

    for idx in range(4):
        world = GridWorld(size=12, start_position=idx, goal_position=11)
        orientation = OrientationCenter(identity=f"civ-agent-{idx}", preferences={"progress": 0.85, "stability": 0.3})
        agent = NCAAgent(world=world, orientation=orientation, meta_observer=MetaObserver())
        system.add_agent(agent)

    events: list[dict[str, object]] = []
    for _ in range(steps):
        events.extend(system.step_all())

    collective = system.collective_state()
    print("=== NCA Civilization Demo (Phase 11) ===")
    print("collective norms:", collective.get("collectivenorms", {}))
    print("collective traditions:", collective.get("collectivetraditionpatterns", {}))
    print("civilization maturity:", collective.get("civilizationmaturityscore", 0.0))
    print("collective culture alignment:", collective.get("collectiveculturealignment", 0.0))
    print("cultural conflicts:", collective.get("collectiveculturalconflict", 0.0))

    return {"events": events, "collective": collective}


if __name__ == "__main__":
    run_demo()
