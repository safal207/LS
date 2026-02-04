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
        time.sleep(0.05)
        return f"ok:{question}"


class TestAgentNoCancel(unittest.TestCase):
    def test_no_cancel_processes_both(self):
        input_queue = queue.Queue()
        output_queue = queue.Queue()

        loop = AgentLoop(
            input_queue,
            output_queue,
            llm=SlowLLM(),
            cancel_on_new_input=False,
        )
        thread = threading.Thread(target=loop.run, daemon=True)
        thread.start()

        input_queue.put({
            "type": "question",
            "text": "first",
            "timestamp": time.time(),
        })
        input_queue.put({
            "type": "question",
            "text": "second",
            "timestamp": time.time(),
        })

        first = output_queue.get(timeout=5)
        second = output_queue.get(timeout=5)
        loop.stop()
        thread.join(timeout=5)

        questions = {first.get("question"), second.get("question")}
        self.assertEqual(questions, {"first", "second"})


if __name__ == "__main__":
    unittest.main()
