import time
import pytest
from unittest.mock import MagicMock
from python.modules.agent.loop import AgentLoop
from python.modules.hexagon_core.temporal_graph import TemporalNode
from codex.causal_memory.amygdala import Amygdala

def test_strengthen_increases_resonance_above_threshold():
    from python.modules.hexagon_core.temporal_graph import TemporalGraph
    graph = TemporalGraph()
    # 100 nodes, 30 > 0.75
    for i in range(70):
        graph.nodes[f"low_{i}"] = TemporalNode(id=f"low_{i}", resonance=0.5)
    for i in range(30):
        graph.nodes[f"high_{i}"] = TemporalNode(id=f"high_{i}", resonance=0.8)

    strengthened = graph.strengthen_strong_links(threshold=0.75, boost=0.1)
    assert strengthened == 30
    assert graph.nodes["high_0"].resonance == 0.9
    assert graph.nodes["low_0"].resonance == 0.5

def test_idle_yoga_triggers_on_timeout():
    # Setup loop with mock LLM/Handler
    loop = AgentLoop(handler=lambda x: "ok")
    loop.temporal.nodes["test"] = TemporalNode(id="test", resonance=0.8)

    # Mock amygdala to return reflection context
    amygdala = MagicMock()
    amygdala.prepare_reflection_context.return_value = {"current_phantom_pain": 0.1, "avg_resolution": 0.5}
    amygdala.visceral.phantom_pain = 0.1
    loop.causal_transitions.amygdala = amygdala

    # Simulate idle for > 300s
    loop.last_input_time = time.time() - 301
    loop.last_yoga_time = 0.0
    loop._transition("idle")

    # This should trigger yoga
    loop._maybe_enter_idle_yoga()

    # Assert resonance increased
    assert loop.temporal.nodes["test"].resonance > 0.8
    assert amygdala.prepare_reflection_context.called

def test_no_strengthen_when_active():
    loop = AgentLoop(handler=lambda x: "ok")
    loop.temporal.nodes["test"] = TemporalNode(id="test", resonance=0.8)

    # Simulate active (recent input)
    loop.last_input_time = time.time() - 10
    loop._transition("idle")

    loop._maybe_enter_idle_yoga()

    # Resonance should NOT increase
    assert loop.temporal.nodes["test"].resonance == 0.8

def test_yoga_cooldown():
    loop = AgentLoop(handler=lambda x: "ok")
    loop.temporal.nodes["test"] = TemporalNode(id="test", resonance=0.8)

    amygdala = MagicMock()
    amygdala.prepare_reflection_context.return_value = {"current_phantom_pain": 0.1, "avg_resolution": 0.5}
    amygdala.visceral.phantom_pain = 0.1
    loop.causal_transitions.amygdala = amygdala

    loop.last_input_time = time.time() - 301
    loop.last_yoga_time = time.time() - 30 # Only 30s since last yoga
    loop._transition("idle")

    loop._maybe_enter_idle_yoga()

    # Should NOT trigger due to cooldown
    assert loop.temporal.nodes["test"].resonance == 0.8

def test_force_yoga_on_high_pain():
    loop = AgentLoop(handler=lambda x: "ok")
    loop.temporal.nodes["test"] = TemporalNode(id="test", resonance=0.8)

    amygdala = MagicMock()
    amygdala.prepare_reflection_context.return_value = {"current_phantom_pain": 0.5, "avg_resolution": 0.5}
    amygdala.visceral.phantom_pain = 0.5 # High pain
    loop.causal_transitions.amygdala = amygdala

    # Even if NOT idle long enough
    loop.last_input_time = time.time() - 10
    loop.last_yoga_time = 0.0

    # Force yoga (triggered by high pain after session)
    loop._maybe_enter_idle_yoga(force=True)

    # Should trigger
    assert loop.temporal.nodes["test"].resonance > 0.8

def test_interaction_populates_nodes():
    loop = AgentLoop(handler=lambda x: "ok")
    # Simulate an interaction
    loop.handle_input("Test resonance population")

    # Nodes should be added to temporal.nodes
    # They should be present even if some transitions are blocked by default Amygdala
    # as long as at least some nodes are created.
    assert len(loop.temporal.nodes) > 0
    for node in loop.temporal.nodes.values():
        assert node.resonance > 0.0
