from __future__ import annotations

from modules.nca.agent import NCAAgent
from modules.nca.meta_observer import MetaObserver
from modules.nca.multiagent import MultiAgentSystem
from modules.nca.orientation import OrientationCenter
from modules.nca.world import GridWorld


def run_demo(steps: int = 10, agents_count: int = 3) -> dict[str, object]:
    system = MultiAgentSystem()
    for idx in range(max(1, agents_count)):
        world = GridWorld(size=14, start_position=idx, goal_position=12, noise_level=0.12 + (0.03 * idx))
        orientation = OrientationCenter(
            identity=f"value-agent-{idx}",
            preferences={"progress": 0.76, "stability": 0.42},
            impulsiveness=0.22,
            stability_preference=0.71,
        )
        system.add_agent(NCAAgent(world=world, orientation=orientation, meta_observer=MetaObserver()), agent_id=f"values-{idx}")

    events: list[dict[str, object]] = []
    for _ in range(steps):
        events.extend(system.step_all())

    collective = system.collective_state()
    print("=== NCA Values & Ethics Demo ===")
    for agent in system.agents:
        event = next((e for e in reversed(events) if e.get("agent_id") == getattr(agent, "agent_id", "")), {})
        values = event.get("values", {}) if isinstance(event, dict) else {}

        print(f"agent={agent.agent_id}")
        print("  action:", event.get("action"))
        print("  value alignment:", round(float(event.get("value_alignment", 0.0)), 3))
        print("  core values:", values.get("core_values", {}))
        print("  ethical constraints:", values.get("ethical_constraints", {}))
        print("  planner value score:", round(float(event.get("details", {}).get("value_score", 0.0)), 3) if isinstance(event.get("details"), dict) else 0.0)

    print("collective value alignment:", collective.get("collectivevaluealignment", 1.0))
    print("collective ethical conflict:", collective.get("collectiveethicalconflict", 0.0))
    print("collective value map:", collective.get("collectivevaluemap", {}))
    return {"events": events, "collective": collective}


if __name__ == "__main__":
    run_demo()
