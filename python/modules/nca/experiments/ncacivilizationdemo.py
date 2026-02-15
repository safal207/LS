from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class NCACivilizationDemo:
    """Runs a compact Phase 11 civilization simulation."""

    world_size: int = 12
    agent_count: int = 4
    steps: int = 8

    def run(self) -> dict[str, Any]:
        # Deferred imports keep this file runnable both as a module and as a script.
        from modules.nca.agent import NCAAgent
        from modules.nca.meta_observer import MetaObserver
        from modules.nca.multiagent import MultiAgentSystem
        from modules.nca.orientation import OrientationCenter
        from modules.nca.world import GridWorld

        system = MultiAgentSystem()
        for idx in range(self.agent_count):
            world = GridWorld(size=self.world_size, start_position=idx, goal_position=self.world_size - 1)
            orientation = OrientationCenter(
                identity=f"civ-agent-{idx}",
                preferences={"progress": 0.85, "stability": 0.3},
            )
            agent = NCAAgent(world=world, orientation=orientation, meta_observer=MetaObserver())
            system.add_agent(agent)

        events: list[dict[str, Any]] = []
        for _ in range(self.steps):
            events.extend(system.step_all())

        collective = system.collective_state()
        print("=== NCA Civilization Demo (Phase 11.1) ===")
        print("collective norms:", collective.get("collectivenorms", {}))
        print("collective traditions:", collective.get("collectivetraditionpatterns", {}))
        print("civilization maturity:", collective.get("civilizationmaturityscore", 0.0))
        print("collective culture alignment:", collective.get("collectiveculturealignment", 0.0))
        print("cultural conflicts:", collective.get("collectiveculturalconflict", 0.0))
        print("collective synergy:", collective.get("collectivesynergy", collective.get("collectivesynergyindex", 0.0)))
        print("collective militocracy:", collective.get("collectivemilitocracy", collective.get("collectivemilitarydiscipline", 0.0)))

        return {"events": events, "collective": collective}


def run_demo(steps: int = 8) -> dict[str, Any]:
    return NCACivilizationDemo(steps=steps).run()


def main() -> None:
    # Script-mode path bootstrap (for: `python python/modules/nca/experiments/ncacivilizationdemo.py`).
    repo_python_root = Path(__file__).resolve().parents[3]
    import sys

    if str(repo_python_root) not in sys.path:
        sys.path.insert(0, str(repo_python_root))

    run_demo()


if __name__ == "__main__":
    main()
