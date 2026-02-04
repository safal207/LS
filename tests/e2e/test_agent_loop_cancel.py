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


class SlowLLM:
    def generate_response(self, question: str, cancel_event=None):
        for _ in range(10):
            if cancel_event is not None and cancel_event.is_set():
                return None
            time.sleep(0.02)
        return f"ok:{question}"

    def format_response(self, response: str) -> str:
        return response


class TestAgentLoopCancel(unittest.TestCase):
    def test_new_input_cancels_previous(self):
        input_queue = queue.Queue()
        output_queue = queue.Queue()
        events = []

        def record(event):
            events.append(event.type)

        loop = AgentLoop(input_queue, output_queue, llm=SlowLLM(), on_event=record)
        thread = threading.Thread(target=loop.run, daemon=True)
        thread.start()

        input_queue.put({
            "type": "question",
            "text": "first",
            "timestamp": time.time(),
        })

        time.sleep(0.05)

        input_queue.put({
            "type": "question",
            "text": "second",
            "timestamp": time.time(),
        })

        payload = output_queue.get(timeout=5)
        loop.stop()
        thread.join(timeout=5)

        self.assertEqual(payload.get("question"), "second")
        self.assertIn("cancelled", events)


if __name__ == "__main__":
    unittest.main()
