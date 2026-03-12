from __future__ import annotations

from dataclasses import dataclass

from ls.cognition.reflection_engine import ReflectionEngine
from ls.memory.memory_graph import MemoryGraph
from modules.shared.event_bus import EventBus


@dataclass
class _Event:
    type: str
    payload: dict


def test_reflection_engine_computes_progress_and_updates_graph():
    graph = MemoryGraph()
    engine = ReflectionEngine(graph)

    engine.process(_Event("action_result", {"goal": "solve", "goal_completion": 0.2, "context": {"action": "plan"}}))
    result = engine.process(_Event("action_result", {"goal": "solve", "goal_completion": 0.6, "context": {"action": "execute", "result": "ok"}}))

    assert result is not None
    assert abs(result.progress - 0.4) < 1e-9
    assert "closer" in result.reason
    assert any(node.node_type == "reflection" for node in graph.nodes.values())


def test_reflection_engine_eventbus_integration():
    graph = MemoryGraph()
    bus = EventBus()
    engine = ReflectionEngine(graph, event_bus=bus)

    bus.publish(_Event("decision_made", {"goal": "g", "goal_completion": 0.1, "context": {}}))
    out = bus.publish(_Event("tool_executed", {"goal": "g", "goal_completion": 0.3, "context": {"result": "r"}}))

    assert out is None
    reflections = [n for n in graph.nodes.values() if n.node_type == "reflection"]
    assert len(reflections) >= 1
