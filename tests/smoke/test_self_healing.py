import pytest
import time
import json
import os
from pathlib import Path
from codex.causal_memory.amygdala import Amygdala
from python.modules.agent.loop import AgentLoop
from python.modules import lthread

class MockLLM:
    def __init__(self, responses=None):
        self.responses = responses or ["I am fine."]
        self.call_count = 0

    def generate_response(self, question, cancel_event=None, messages=None):
        res = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return res

    def format_response(self, response):
        return response

@pytest.fixture
def amygdala(tmp_path):
    # Ensure orientation_invariants.json exists in root for tests
    inv_file = Path("orientation_invariants.json")
    if not inv_file.exists():
        inv_file.write_text(json.dumps({
            "core_rules": [
                {"invariant": "phantom_pain_max", "max": 0.8, "action": "block"},
                {"invariant": "axis_resonance_min", "value": 0.6, "action": "rollback"}
            ]
        }))

    return Amygdala(user_id="test_healer", memory_base_dir=tmp_path, persist_state=True)

def test_axis_drift_prevented(amygdala):
    # Set a valid initial state and save it as "last valid"
    amygdala.state = 0.2 # Resonance 0.8
    amygdala.last_valid_snapshot = amygdala.to_snapshot()
    amygdala._persist_state()

    # Simulate drift
    amygdala.state = 0.7 # Resonance 0.3, below 0.6 threshold

    # Trigger self-healing
    violations = amygdala.self_heal()

    assert "axis_resonance_min" in violations
    assert amygdala.state == 0.2 # Restored

def test_injection_triggers_rollback(amygdala):
    # Setup last valid
    amygdala.state = 0.1 # Resonance 0.9
    amygdala.last_valid_snapshot = amygdala.to_snapshot()
    amygdala._persist_state()

    # We can't easily trigger a rollback via detect_prompt_injection
    # because it currently just blocks.
    # But if an injection caused a state violation:
    amygdala.state = 0.9 # Resonance 0.1

    llm = MockLLM()
    # AgentLoop uses amygdala inside causal_transitions
    loop = AgentLoop(llm=llm, amygdala=amygdala)

    # We need to mock the event emitting to catch 'soul_healed'
    events = []
    def on_event(ev):
        events.append(ev)
    loop.on_event = on_event

    # Process a normal item, but amygdala starts in invalid state
    # Wait a bit for threads if necessary, but handle_input is synchronous here
    # since we didn't start loop.run()
    loop.handle_input("Help me")

    # self_heal should have been called in _process_item
    assert any(e.type == "soul_healed" for e in events) or amygdala.state == 0.1
    assert amygdala.state == 0.1 # Restored

def test_hallucination_detected_and_fixed(monkeypatch):
    # Hallucination detection is in lthread.verify_trace
    # Let's mock it to return False once
    verify_calls = []
    def mock_verify(trace):
        verify_calls.append(trace)
        return len(verify_calls) > 1 # False first time, True second time

    monkeypatch.setattr(lthread, "verify_trace", mock_verify)

    # Setup valid state to avoid Amygdala blocking the transition
    # Use high thresholds to avoid blocking
    amygdala = Amygdala(max_axis_delta=2.0, threshold_overload=2.0)
    amygdala.state = 0.1 # Resonance 0.9
    amygdala.visceral.phantom_pain = 0.1
    amygdala.last_valid_snapshot = amygdala.to_snapshot()

    llm = MockLLM(["I am hallucinating UNKNOWN_FACT", "I am fixed now"])
    loop = AgentLoop(llm=llm, amygdala=amygdala)

    events = []
    def on_event(ev):
        events.append(ev)
    loop.on_event = on_event

    loop.handle_input("Tell me a fact")

    # Should see liminal_transition with hallucination_detected
    assert any(e.type == "liminal_transition" and e.payload.get("trigger") == "hallucination_detected" for e in events)
    # LLM should have been called twice
    assert llm.call_count == 2

def test_healing_preserves_important_states(amygdala):
    # Setup valid state with some session-specific data
    amygdala.state = 0.1
    amygdala.interaction_count = 10
    amygdala.last_valid_snapshot = amygdala.to_snapshot()
    amygdala._persist_state()

    # Drift
    amygdala.state = 0.8
    amygdala.interaction_count = 11

    amygdala.self_heal()

    assert amygdala.state == 0.1
    # interaction_count was preserved in the snapshot, so it's also restored?
    # Actually, to_snapshot includes interaction_count.
    # If we want to preserve it, we should maybe excluded it from snapshot or restore it manually.
    # But usually rollback means FULL rollback.
    assert amygdala.interaction_count == 10
