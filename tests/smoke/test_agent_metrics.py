import queue
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from agent.loop import AgentLoop


class DummyLLM:
    def generate_response(self, question: str, cancel_event=None):
        return "ok"


class TestAgentMetrics(unittest.TestCase):
    def test_metrics_increment(self):
        output_queue = queue.Queue()
        loop = AgentLoop(output_queue=output_queue, llm=DummyLLM())

        loop.handle_input("first")
        loop.handle_input("second")

        self.assertEqual(loop.metrics["inputs"], 2)
        self.assertEqual(loop.metrics["outputs"], 2)
        self.assertGreaterEqual(loop.metrics["last_latency"], 0.0)


if __name__ == "__main__":
    unittest.main()
