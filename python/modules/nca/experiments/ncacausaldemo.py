from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.nca.agent import NCAAgent
from modules.nca.orientation import OrientationCenter
from modules.nca.world import GridWorld


def run_demo(steps: int = 30) -> list[dict[str, object]]:
    """Run NCA Phase 2 demo with causal traps and causal-aware planning."""
    world = GridWorld(
        size=15,
        start_position=0,
        goal_position=13,
        noise_level=0.2,
        slippery_zone=(4, 7, 10),
        blocked_zone=(5, 11),
        reward_zone=(12, 13),
    )
    orientation = OrientationCenter(
        identity="nca-phase-2-agent",
        invariants={"preserve_identity": True, "avoid_idle_loops": True},
        preferences={"progress": 1.0, "stability": 0.2},
        risk_tolerance=0.4,
        exploration_ratio=0.35,
        impulsiveness=0.25,
        stability_preference=0.75,
    )
    agent = NCAAgent(world=world, orientation=orientation)

    log: list[dict[str, object]] = []
    for _ in range(steps):
        event = agent.step()
        log.append(event)
        print(
            f"t={event['t']:02d} action={event['action']:<5} "
            f"pos={event['position_after']} score={event['score']:.2f} "
            f"causal={event['causal_score']:.2f} "
            f"signals={[s['type'] for s in event['signals']]}"
        )

    print("\nCausal graph growth:", event["causal_graph"]["transition_count"])
    print("Final causal edges:", len(event["causal_graph"]["edges"]))
    return log


if __name__ == "__main__":
    run_demo(steps=30)
