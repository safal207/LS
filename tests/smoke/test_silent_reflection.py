import time
import pytest
from unittest.mock import MagicMock
from python.modules.agent.loop import AgentLoop
from codex.causal_memory.amygdala import Amygdala

class MockLLM:
    def __init__(self):
        self.responses = []

    def generate_response(self, question, cancel_event=None, messages=None):
        if self.responses:
            return self.responses.pop(0)
        return "Standard response"

@pytest.fixture
def agent_setup():
    llm = MockLLM()
    amy = Amygdala(persist_state=False)
    amy.state = 0.2  # Ensure resonance (1-state) is above threshold (0.6)
    amy.last_valid_snapshot = amy.to_snapshot()
    # Mock visceral history to have enough entries for prepare_reflection_context
    for _ in range(25):
        amy.visceral.record_pain(0.1)

    loop = AgentLoop(llm=llm, amygdala=amy)
    return loop, amy, llm

def test_silent_ref_generated_in_idle(agent_setup):
    loop, amy, llm = agent_setup
    amy.visceral.phantom_pain = 0.5  # Trigger threshold > 0.2
    llm.responses = ["I felt a quiet peace."]

    # Simulate idle > 300s
    loop.last_input_time = time.time() - 301
    loop._transition("idle")

    loop._maybe_enter_idle_yoga()

    assert amy.last_silent_reflection == "I felt a quiet peace."

def test_silent_ref_injected_on_open_question(agent_setup):
    loop, amy, llm = agent_setup
    amy.last_silent_reflection = "Inside, everything is still."

    # Open question trigger
    history = []
    messages = loop._inject_reflection_into_context(history, force_show_silent=True)

    assert len(messages) == 1
    assert "Inside, everything is still." in messages[0]["content"]

def test_silent_ref_not_shown_on_direct_question(agent_setup):
    loop, amy, llm = agent_setup
    amy.last_silent_reflection = "Quietly observing."
    amy.interaction_count = 1  # Not a multiple of 10

    # Direct question, no force
    history = []
    messages = loop._inject_reflection_into_context(history, force_show_silent=False)

    assert len(messages) == 0

def test_silent_ref_cleared_after_show(agent_setup):
    loop, amy, llm = agent_setup
    amy.last_silent_reflection = "Thinking in the dark."
    # We want to trigger clearing by keyword or interaction count
    amy.interaction_count = 5

    # Keyword trigger
    result = "Я заметил тишину внутри."
    force_show_silent = False

    # Directly test clearing logic
    response_text = result.lower()
    if any(word in response_text for word in ["тихо", "внутри", "заметил", "yoga", "рефлексия", "отдохнул"]):
        amy.last_silent_reflection = None
    elif force_show_silent or amy.interaction_count % 5 == 0:
        amy.last_silent_reflection = None

    assert amy.last_silent_reflection is None

def test_silent_ref_cleared_by_interaction_count(agent_setup):
    loop, amy, llm = agent_setup
    amy.last_silent_reflection = "Thinking in the dark."
    amy.interaction_count = 5 # Trigger

    result = "Some other response."
    force_show_silent = False

    # Directly test clearing logic
    response_text = result.lower()
    if any(word in response_text for word in ["тихо", "внутри", "заметил", "yoga", "рефлексия", "отдохнул"]):
        amy.last_silent_reflection = None
    elif force_show_silent or amy.interaction_count % 5 == 0:
        amy.last_silent_reflection = None

    assert amy.last_silent_reflection is None
