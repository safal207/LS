import queue
import threading
import time
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


class TestAgentLoopFlow(unittest.TestCase):
    def test_loop_emits_events_and_idle(self):
        input_queue = queue.Queue()
        output_queue = queue.Queue()
        events = []

        def record(event):
            events.append(event.type)

        loop = AgentLoop(input_queue, output_queue, llm=DummyLLM(), on_event=record)
        thread = threading.Thread(target=loop.run, daemon=True)
        thread.start()

        input_queue.put({
            "type": "question",
            "text": "hi",
            "timestamp": time.time(),
        })

        output_queue.get(timeout=5)
        loop.stop()
        thread.join(timeout=5)

        self.assertIn("input_received", events)
        self.assertIn("llm_started", events)
        self.assertIn("llm_finished", events)
        self.assertIn("output_ready", events)
        self.assertEqual(loop.temporal.state, "idle")


if __name__ == "__main__":
    unittest.main()
