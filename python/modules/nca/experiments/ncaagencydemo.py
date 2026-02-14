from __future__ import annotations

import sys
from pathlib import Path


def run_demo(steps: int = 8) -> dict[str, object]:
    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from modules.nca.agent import NCAAgent
    from modules.nca.meta_observer import MetaObserver
    from modules.nca.multiagent import MultiAgentSystem
    from modules.nca.orientation import OrientationCenter
    from modules.nca.world import GridWorld

    system = MultiAgentSystem()

    for idx in range(3):
        world = GridWorld(size=12, start_position=idx, goal_position=11)
        orientation = OrientationCenter(identity=f"agency-agent-{idx}", preferences={"progress": 0.9, "stability": 0.3})
        agent = NCAAgent(world=world, orientation=orientation, meta_observer=MetaObserver())
        system.add_agent(agent)

    events: list[dict[str, object]] = []
    for _ in range(steps):
        events.extend(system.step_all())

    collective = system.collective_state()
    latest = events[-1] if events else {}
    print("=== NCA Emergent Agency Demo ===")
    print("agency_level:", latest.get("identity_core", {}).get("agency_level"))
    print("identity_integrity:", latest.get("identity_core", {}).get("identity_integrity"))
    print("initiative:", latest.get("initiative"))
    print("longtermgoals:", latest.get("identity_core", {}).get("longtermgoals"))
    print("collective agency:", collective.get("collectiveagencylevel"))
    return {
        "events": events,
        "collective": collective,
    }


if __name__ == "__main__":
    run_demo()
