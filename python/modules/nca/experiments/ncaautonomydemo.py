from __future__ import annotations

from modules.nca.agent import NCAAgent
from modules.nca.meta_observer import MetaObserver
from modules.nca.multiagent import MultiAgentSystem
from modules.nca.orientation import OrientationCenter
from modules.nca.world import GridWorld


def run_demo(steps: int = 10, agents_count: int = 3) -> dict[str, object]:
    system = MultiAgentSystem()
    for idx in range(max(1, agents_count)):
        world = GridWorld(size=14, start_position=idx, goal_position=12, noise_level=0.15 + (0.04 * idx))
        orientation = OrientationCenter(
            identity=f"autonomy-agent-{idx}",
            preferences={"progress": 0.8, "stability": 0.38},
            impulsiveness=0.28,
            stability_preference=0.67,
        )
        system.add_agent(NCAAgent(world=world, orientation=orientation, meta_observer=MetaObserver()), agent_id=f"autonomy-{idx}")

    events: list[dict[str, object]] = []
    for _ in range(steps):
        events.extend(system.step_all())

    collective = system.collective_state()
    print("=== NCA Autonomy Demo ===")
    for agent in system.agents:
        event = next((e for e in reversed(events) if e.get("agent_id") == getattr(agent, "agent_id", "")), {})
        autonomy = event.get("autonomy", {}) if isinstance(event, dict) else {}

        print(f"agent={agent.agent_id}")
        print("  action:", event.get("action"))
        print("  autonomy level:", round(float(autonomy.get("autonomy_level", 0.0)), 3))
        print("  primary strategy:", event.get("primary_strategy", {}))
        print("  self-directed goals:", autonomy.get("selfdirectedgoals", []))
        print("  strategy influence score:", round(float(event.get("details", {}).get("strategy_score", 0.0)), 3) if isinstance(event.get("details"), dict) else 0.0)

    print("collective autonomy level:", collective.get("collectiveautonomylevel", 0.0))
    print("collective strategy map:", collective.get("collectivestrategymap", {}))
    print("collective autonomy conflict:", collective.get("collectiveautonomyconflict", 0.0))
    return {"events": events, "collective": collective}


if __name__ == "__main__":
    run_demo()
