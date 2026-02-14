from __future__ import annotations

import sys
from pathlib import Path

from modules.nca.agent import NCAAgent
from modules.nca.meta_observer import MetaObserver
from modules.nca.multiagent import MultiAgentSystem
from modules.nca.orientation import OrientationCenter
from modules.nca.world import GridWorld

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run_demo(steps: int = 8) -> dict[str, object]:
    system = MultiAgentSystem()

    for idx in range(4):
        world = GridWorld(size=12, start_position=idx, goal_position=11)
        orientation = OrientationCenter(identity=f"ma-agent-{idx}", preferences={"progress": 0.9, "stability": 0.2})
        agent = NCAAgent(world=world, orientation=orientation, meta_observer=MetaObserver())
        system.add_agent(agent)

    events: list[dict[str, object]] = []
    for _ in range(steps):
        events.extend(system.step_all())

    collective = system.collective_state()
    print("=== NCA Multi-Agent Demo ===")
    print(f"agents: {len(system.agents)}")
    print("collective causal graph:", collective["shared_causal"])
    print("collective signals:", collective["recent_signals"][-5:])
    print("coordinated trajectories/events sample:", events[-4:])
    print("emergent behavior score:", collective["collective_progress_score"])
    return {
        "events": events,
        "collective": collective,
    }


if __name__ == "__main__":
    run_demo()
