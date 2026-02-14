from __future__ import annotations

import random

from modules.nca.agent import NCAAgent
from modules.nca.orientation import OrientationCenter
from modules.nca.world import GridWorld


def run_stress_test(steps: int = 30, seed: int = 7) -> list[dict[str, object]]:
    rng = random.Random(seed)
    world = GridWorld(size=14, start_position=0, goal_position=12, noise_level=0.55)
    orientation = OrientationCenter(
        identity="nca-phase-1.5-agent",
        invariants={"preserve_identity": True, "avoid_idle_loops": True},
        preferences={"progress": 1.0, "stability": 0.25},
        risk_tolerance=0.45,
        exploration_ratio=0.4,
        impulsiveness=0.25,
        stability_preference=0.75,
    )
    agent = NCAAgent(world=world, orientation=orientation)

    log: list[dict[str, object]] = []
    for _ in range(steps):
        if rng.random() < 0.2:
            world.noise_level = min(0.9, world.noise_level + 0.1)
        elif rng.random() < 0.2:
            world.noise_level = max(0.1, world.noise_level - 0.1)

        event = agent.step()
        log.append(event)

        report = event["analysis"]["report"]
        print(
            f"t={event['t']:02d} action={event['action']:<5} "
            f"self_consistency={report.self_consistency:.2f} "
            f"uncertainty={event['uncertainty']:.2f} "
            f"confidence={event['confidence']:.2f} "
            f"trajectory_score={event['score']:.2f} "
            f"signals={[s['type'] for s in event['signals']]}"
        )

    return log


if __name__ == "__main__":
    run_stress_test(steps=30)
