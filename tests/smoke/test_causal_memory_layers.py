import queue
import sys
from pathlib import Path

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


def test_agent_loop_exposes_causal_metrics() -> None:
    output_queue: queue.Queue = queue.Queue()
    loop = AgentLoop(output_queue=output_queue, llm=DummyLLM())

    loop.handle_input("mission resonance care")
    payload = output_queue.get_nowait()

    assert "causal_stability_ok" in payload
    assert "causal_resonance" in payload
