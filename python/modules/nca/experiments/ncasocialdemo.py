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


def run_demo(steps: int = 10) -> dict[str, object]:
    system = MultiAgentSystem()

    profiles = [
        {"progress": 0.92, "stability": 0.18},
        {"progress": 0.78, "stability": 0.38},
        {"progress": 0.68, "stability": 0.55},
        {"progress": 0.84, "stability": 0.3},
    ]

    for idx, prefs in enumerate(profiles):
        world = GridWorld(size=14, start_position=idx, goal_position=13)
        orientation = OrientationCenter(identity=f"social-agent-{idx}", preferences=prefs)
        agent = NCAAgent(world=world, orientation=orientation, meta_observer=MetaObserver())
        system.add_agent(agent)

    events: list[dict[str, object]] = []
    for _ in range(steps):
        events.extend(system.step_all())

    collective = system.collective_state()
    print("=== NCA Social Cognition & Cooperation Demo ===")
    print(f"agents: {len(system.agents)}")
    print(f"collective social alignment: {collective.get('collectiveethicalalignment', 0.0):.3f}")
    print(f"collective cooperation score: {collective.get('collectivecooperationscore', 0.0):.3f}")
    print(f"collective social conflict: {collective.get('collectivesocialconflict', 0.0):.3f}")
    print("collective values:", collective.get("collectivevaluemap", {}))
    print("collective intents:", collective.get("collectiveintentmap", {}))
    print("social map:", collective.get("collectivesocialmap", {}))
    print("recent social events:", events[-4:])

    return {
        "events": events,
        "collective": collective,
    }


if __name__ == "__main__":
    run_demo()
