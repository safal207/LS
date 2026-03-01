import time
import pytest
from unittest.mock import MagicMock
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
    amygdala.metabolism.nutrient_pool = 1.0  # Big pool for guaranteed boost

    mock_agent._enter_sleep_mode()

    # feed_growth reduces state (max boost 0.1)
    assert amygdala.state < 0.5
    assert amygdala.state >= 0.4

def test_sleep_prunes_and_composts(mock_agent):
    amygdala = mock_agent.causal_transitions.amygdala
    mock_agent.temporal.nodes["weak"] = TemporalNode(id="weak", resonance=0.1)
    mock_agent.temporal.nodes["strong"] = TemporalNode(id="strong", resonance=0.9)

    old_pool = amygdala.metabolism.nutrient_pool

    mock_agent._enter_sleep_mode()

    assert "weak" not in mock_agent.temporal.nodes
    assert "strong" in mock_agent.temporal.nodes
    # Composted pruned node should increase nutrient pool (before feed_growth uses it)
    # Since _enter_sleep_mode calls feed_growth after digestion but before pruning in my impl...
    # Wait, the blueprint said:
    # 1. Digest
    # 2. Feed
    # 3. Immune
    # 4. Prune
    # So pruned nodes nutrient will be available for NEXT sleep/growth cycle.
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
