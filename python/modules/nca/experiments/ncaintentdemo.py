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


def run_demo(steps: int = 10, agents_count: int = 3) -> dict[str, object]:
    system = MultiAgentSystem()
    for idx in range(max(1, agents_count)):
        world = GridWorld(size=14, start_position=idx, goal_position=12, noise_level=0.18 + (0.04 * idx))
        orientation = OrientationCenter(
            identity=f"intent-agent-{idx}",
            preferences={"progress": 0.82, "stability": 0.35},
            impulsiveness=0.31,
            stability_preference=0.69,
        )
        system.add_agent(NCAAgent(world=world, orientation=orientation, meta_observer=MetaObserver()), agent_id=f"intent-{idx}")

    events: list[dict[str, object]] = []
    for _ in range(steps):
        events.extend(system.step_all())

    collective = system.collective_state()
    print("=== NCA Intentionality Demo ===")
    for agent in system.agents:
        event = next((e for e in reversed(events) if e.get("agent_id") == getattr(agent, "agent_id", "")), {})
        intents = event.get("intents", []) if isinstance(event, dict) else []
        primary_intent = event.get("primary_intent", {}) if isinstance(event, dict) else {}

        print(f"agent={agent.agent_id}")
        print("  action:", event.get("action"))
        print("  primary intent:", primary_intent)
        print("  intent strength:", agent.intentengine.intent_strength)
        print("  intent alignment:", agent.intentengine.intent_alignment)
        print("  intents formed:")
        for intent in intents:
            print(
                "   -",
                intent.get("name"),
                "strength=", round(float(intent.get("strength", 0.0)), 3),
                "alignment=", round(float(intent.get("alignment", 0.0)), 3),
            )

    print("collective intents:", collective.get("collectiveintentmap", {}))
    print("collective intent alignment:", collective.get("collectiveintentalignment", 1.0))
    print("collective intent conflict:", collective.get("collectiveintentconflict", 0.0))
    return {"events": events, "collective": collective}


if __name__ == "__main__":
    run_demo()
