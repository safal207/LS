from __future__ import annotations

from modules.nca.agent import NCAAgent
from modules.nca.orientation import OrientationCenter
from modules.nca.world import GridWorld


def run_demo(steps: int = 20) -> list[dict[str, object]]:
    """Run a single-agent NCA Phase 1 demonstration."""
    world = GridWorld(size=12, start_position=0, goal_position=10)
    orientation = OrientationCenter(
        identity="nca-prototype-agent",
        invariants={"preserve_identity": True},
        preferences={"progress": 1.0, "stability": 0.1},
    )
    agent = NCAAgent(world=world, orientation=orientation)

    log: list[dict[str, object]] = []
    for _ in range(steps):
        event = agent.step()
        log.append(event)
        print(
            f"t={event['t']:02d} action={event['action']:<5} "
            f"pos={event['position_after']} score={event['score']:.2f} "
            f"goal={event['goal_reached']}"
        )

    print("\\nFinal world state:", world.state())
    print("Final orientation preferences:", orientation.preferences)
    return log


if __name__ == "__main__":
    run_demo(steps=20)
