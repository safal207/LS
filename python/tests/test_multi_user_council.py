from __future__ import annotations

import os
from unittest.mock import MagicMock

from ls.agent_shell.cognitive_state import CognitiveStateBridge
from ls.agent_shell.mcp_resources import MCPResourceRegistry
from ls.agent_shell.mcp_tools import MCPToolRegistry
from modules.council.council_engine import RelationalCouncilEngine
from modules.graph.models import RelationalSelf
from modules.shared.event_bus import EventBus


def test_council_engine_multi_user_live_mode_broadcasts() -> None:
    bus = EventBus()
    seen: list[str] = []
    bus.subscribe("council.live.shared_state_updated", lambda event: seen.append(event.type))
    engine = RelationalCouncilEngine(event_bus=bus)

    outcome = engine.run_mode(
        mode="multi-user-live",
        relational_self=RelationalSelf(last_emotional_state="supportive", bond_strength=0.78, emotional_decay=0.91),
    )

    assert outcome["mode"] == "multi-user-live"
    assert outcome["real_time_sync"] is True
    assert seen == ["council.live.shared_state_updated"]


def test_join_live_council_tool_and_resource(tmp_path) -> None:
    manager = MagicMock()
    manager.get_resonance_snapshot = MagicMock(return_value=[])
    manager.get_alignment_current = MagicMock(return_value={"alignment_state": "ok"})
    os.environ["GRAPH_MEMORY_STORE_PATH"] = str(tmp_path / "cases.jsonl")
    bridge = CognitiveStateBridge(task_manager=manager)
    tools = MCPToolRegistry(task_manager=manager, cognitive_state=bridge)
    resources = MCPResourceRegistry(task_manager=manager, cognitive_state=bridge)

    names = [row["name"] for row in tools.list_tools()]
    assert "join_live_council" in names

    joined = tools.call_tool(
        "join_live_council",
        {"session_id": "session-1", "participant_id": "user-2", "consent": True},
    )
    assert joined["joined"] is True
    assert "user-2" in joined["session"]["participants"]

    live = resources.read_resource("council/live", {"session_id": "session-1"})
    assert live["resource"] == "council/live"
    assert "user-2" in list(live.get("participants") or [])
