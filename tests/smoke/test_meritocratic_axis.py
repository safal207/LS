import pytest
from unittest.mock import MagicMock
from python.modules.hexagon_core.temporal_graph import TemporalGraph, TemporalNode
from python.modules.agent.loop import AgentLoop
from codex.causal_memory.amygdala import Amygdala

def test_axis_selects_highest_resonance():
    graph = TemporalGraph()
    node1 = TemporalNode(id="n1", resonance=0.5)
    node2 = TemporalNode(id="n2", resonance=0.8)
    node3 = TemporalNode(id="n3", resonance=0.6, harmony_bonus=0.5) # 0.6 * 1.5 = 0.9

    graph.nodes = {"n1": node1, "n2": node2, "n3": node3}

    axis = graph.get_meritocratic_axis()
    assert axis.id == "n3"

def test_align_to_axis():
    graph = TemporalGraph()
    node_axis = TemporalNode(id="axis", resonance=0.8)
    graph.nodes = {"axis": node_axis}

    new_node = TemporalNode(id="new", resonance=0.7)
    synergy = graph.align_to_axis(new_node)

    assert synergy > 0
    assert new_node.resonance > 0.7

def test_self_proposal_generated_in_idle():
    llm = MagicMock()
    llm.generate_response.return_value = "This is a very important self-proposal for the user."

    amygdala = Amygdala(persist_state=False)
    amygdala.last_silent_reflection = "I feel calm."

    loop = AgentLoop(llm=llm, amygdala=amygdala)
    loop.temporal.nodes["axis"] = TemporalNode(id="axis", resonance=0.9)

    # Mocking time and state to trigger idle yoga
    loop.last_input_time = 0
    loop.last_yoga_time = 0
    loop._transition("idle")

    loop._maybe_enter_idle_yoga()

    assert amygdala.last_proposal == "This is a very important self-proposal for the user."

def test_proposal_shown_on_open_question():
    amygdala = Amygdala(persist_state=False)
    amygdala.last_proposal = "Let's work on harmony."

    loop = AgentLoop(llm=MagicMock(), amygdala=amygdala)

    # Test with open question
    history = [{"role": "user", "content": "How are you?"}]
    new_history = loop._inject_reflection_into_context(history, question="Как дела?")

    assert "Let's work on harmony." in new_history[0]["content"]
    assert amygdala.last_proposal is None # Cleared after show

def test_no_proposal_on_direct_task():
    amygdala = Amygdala(persist_state=False)
    amygdala.last_proposal = "Let's work on harmony."

    loop = AgentLoop(llm=MagicMock(), amygdala=amygdala)

    # Test with direct task
    history = [{"role": "user", "content": "Do the laundry."}]
    new_history = loop._inject_reflection_into_context(history, question="Сделай прачечную")

    # Proposal should NOT be in context
    for msg in new_history:
        if msg["role"] == "system":
            assert "Let's work on harmony." not in msg["content"]
    assert amygdala.last_proposal == "Let's work on harmony." # Not cleared
