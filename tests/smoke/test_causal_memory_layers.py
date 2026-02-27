import queue
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from python.modules.agent.loop import AgentLoop
from python.modules.memory.causal import CausalMemory


class DummyLLM:
    def generate_response(self, question: str):
        return "ok"


def test_causal_memory_linear_layers() -> None:
    memory = CausalMemory()
    customer_id = memory.add_intent("mission resonance care")
    consumer_id = memory.transition_down(customer_id, "mission resonance care", "Consumer")
    execution_id = memory.transition_down(consumer_id, "mission resonance plan", "Execution")
    stability_id = memory.transition_down(execution_id, "mission resonance monitor", "Stability")

    assert memory.check_resonance(stability_id) > 0.0
    assert memory.stabilize(stability_id) is True
    assert memory.get_axis_position(customer_id) == pytest.approx(-1.0)
    assert memory.get_axis_position(consumer_id) == pytest.approx(-0.33)
    assert memory.get_axis_position(execution_id) == pytest.approx(0.33)
    assert memory.get_axis_position(stability_id) == pytest.approx(1.0)


def test_causal_memory_blocks_low_resonance() -> None:
    memory = CausalMemory()
    customer_id = memory.add_intent("mission resonance care")

    with pytest.raises(Exception):
        memory.transition_down(customer_id, "banana quantum trumpet", "Consumer")


def test_agent_loop_exposes_causal_metrics() -> None:
    output_queue: queue.Queue = queue.Queue()
    loop = AgentLoop(output_queue=output_queue, llm=DummyLLM())

    loop.handle_input("mission resonance care")
    payload = output_queue.get_nowait()

    assert "causal_stability_ok" in payload
    assert "causal_resonance" in payload
    assert "causal_axis_position" in payload
    assert payload["amygdala_status"] == "stable"
    assert 0.0 <= payload["amygdala_state"] <= 1.0
    assert payload["amygdala_history_size"] >= 1


def test_agent_loop_blocks_threatening_transition() -> None:
    output_queue: queue.Queue = queue.Queue()
    loop = AgentLoop(output_queue=output_queue, llm=DummyLLM())

    loop.causal_transitions.amygdala.state = 0.9
    loop.causal_transitions.amygdala.adaptive_bias = 0.2

    loop.handle_input("threat danger panic")
    payload = output_queue.get_nowait()

    assert payload["amygdala_status"] == "blocked"
    assert payload["amygdala_reason"] in {"threat", "low_resonance", "overload"}
    assert payload["causal_rollback_layer"] in {"Customer", "Consumer", "Execution"}
    assert payload["amygdala_state"] >= 0.65
    assert payload["amygdala_history_size"] >= 1
    assert "спокойнее" in payload["response"].lower()
