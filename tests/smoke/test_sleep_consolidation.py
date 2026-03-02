import time
import pytest
import sys
from unittest.mock import MagicMock

# Mock SLEEP_CONFIG to avoid environment-specific import issues with PyYAML
class MockSleepConfig:
    idle_timeout = 1800
    prune_threshold = 0.2
    active_window = 200
    reflection_energy = 0.05
    compost_boost_per_node = 0.01
    immune_threshold = 0.7
    immune_decay = 0.9

mock_config = MagicMock()
mock_config.SLEEP_CONFIG = MockSleepConfig()
sys.modules["modules.config"] = mock_config

from python.modules.agent.loop import AgentLoop
from codex.causal_memory.amygdala import Amygdala
from python.modules.hexagon_core.temporal_graph import TemporalNode

@pytest.fixture
def mock_agent():
    amygdala = Amygdala(persist_state=False)
    # Ensure metabolism has something to work with
    amygdala.last_silent_reflection = "Test reflection for consolidation"

    loop = AgentLoop(
        handler=lambda x: "response",
        amygdala=amygdala,
        temporal_enabled=True
    )
    # Mock LLM to avoid external calls
    loop.llm = MagicMock()
    return loop

def test_sleep_consolidates_reflections(mock_agent):
    amygdala = mock_agent.causal_transitions.amygdala
    assert amygdala.last_silent_reflection == "Test reflection for consolidation"
    assert len(amygdala.metabolism.lessons) == 0

    mock_agent._enter_sleep_mode()

    assert amygdala.last_silent_reflection is None
    assert len(amygdala.metabolism.lessons) == 1
    assert "Урок из тишины: Test reflection" in amygdala.metabolism.lessons[0]

def test_sleep_boosts_axis(mock_agent):
    amygdala = mock_agent.causal_transitions.amygdala
    amygdala.state = 0.5
    # Ensure there is a reflection to digest and gain energy
    amygdala.last_silent_reflection = "Something to digest"

    mock_agent._enter_sleep_mode()

    # feed_growth reduces state during sleep using the cycle energy
    assert amygdala.state < 0.5

def test_sleep_prunes_and_composts(mock_agent):
    amygdala = mock_agent.causal_transitions.amygdala
    mock_agent.temporal.nodes["weak"] = TemporalNode(id="weak", resonance=0.1)
    mock_agent.temporal.nodes["strong"] = TemporalNode(id="strong", resonance=0.9)

    mock_agent._enter_sleep_mode()

    assert "weak" not in mock_agent.temporal.nodes
    assert "strong" in mock_agent.temporal.nodes
    # Composted pruned node should increase nutrient pool and be logged in waste_bin
    assert any(item["type"] == "pruned" for item in amygdala.metabolism.waste_bin)

def test_manual_sleep_command(mock_agent):
    # Mock _enter_sleep_mode to see if it's called
    mock_agent._enter_sleep_mode = MagicMock()

    item = {"type": "question", "text": "/sleep"}
    mock_agent._process_item(item, task_id=1, cancel_event=MagicMock())

    mock_agent._enter_sleep_mode.assert_called_once()

def test_auto_sleep_trigger(mock_agent):
    mock_agent._enter_sleep_mode = MagicMock()

    # Mock idle for > 30 mins
    mock_agent.last_input_time = time.time() - 2000
    mock_agent._maybe_enter_sleep_mode()

    mock_agent._enter_sleep_mode.assert_called_once()
