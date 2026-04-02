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
    def generate_response(self, question: str):
        return "ok"

    def format_response(self, response: str) -> str:
        return response


class TestAgentLoop(unittest.TestCase):
    def test_handle_input_sets_idle(self):
        output_queue = queue.Queue()
        loop = AgentLoop(output_queue=output_queue, llm=DummyLLM())

        loop.handle_input("hi")

        payload = output_queue.get_nowait()
        self.assertIn("response", payload)
        self.assertIn("mode_explanation", payload)
        self.assertIsNotNone(loop.temporal)
        self.assertEqual(loop.temporal.state, "idle")

    def test_subconscious_pass_creates_latest_insight(self):
        loop = AgentLoop(output_queue=queue.Queue(), llm=DummyLLM())
        loop.memory["history"] = [
            {"role": "user", "content": "how does this work"},
            {"role": "assistant", "content": "answer"},
            {"role": "user", "content": "why does it fail on edge cases"},
            {"role": "assistant", "content": "answer"},
        ]

        loop._run_subconscious_pass()

        latest = loop.memory.get("subconscious_latest")
        self.assertIsInstance(latest, dict)
        self.assertIn("suggested_mode", latest)
        self.assertIn("route", latest)


if __name__ == "__main__":
    unittest.main()
