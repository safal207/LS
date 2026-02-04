import queue
import sys
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from agent.loop import AgentLoop


class BlockingLLM:
    def __init__(self, started: threading.Event, allow: threading.Event):
        self.started = started
        self.allow = allow

    def generate_response(self, question: str, cancel_event=None):
        self.started.set()
        self.allow.wait(timeout=1.0)
        return "ok"

    def format_response(self, response: str) -> str:
        return response


class TestAgentTaskDone(unittest.TestCase):
    def test_join_returns_before_processing_finishes(self):
        input_queue = queue.Queue()
        output_queue = queue.Queue()
        started = threading.Event()
        allow = threading.Event()
        loop = AgentLoop(
            input_queue=input_queue,
            output_queue=output_queue,
            llm=BlockingLLM(started, allow),
        )

        thread = threading.Thread(target=loop.run, daemon=True)
        thread.start()

        input_queue.put({
            "type": "question",
            "text": "hello",
            "timestamp": time.time(),
        })

        self.assertTrue(started.wait(timeout=1.0))

        join_thread = threading.Thread(target=input_queue.join)
        join_thread.start()
        join_thread.join(timeout=0.5)

        self.assertFalse(join_thread.is_alive(), "queue.join() should return before processing completes")
        self.assertTrue(output_queue.empty())

        allow.set()
        output_queue.get(timeout=2.0)
        loop.stop()
        thread.join(timeout=2.0)


if __name__ == "__main__":
    unittest.main()
