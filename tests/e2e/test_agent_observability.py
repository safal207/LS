import io
import json
import queue
import threading
import time
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from agent.loop import AgentLoop
from agent.sinks import PrintSink


class SlowLLM:
    def generate_response(self, question: str, cancel_event=None):
        for _ in range(10):
            if cancel_event is not None and cancel_event.is_set():
                return None
            time.sleep(0.02)
        return f"ok:{question}"


class TestAgentObservability(unittest.TestCase):
    def test_observability_events(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            input_queue = queue.Queue()
            output_queue = queue.Queue()
            loop = AgentLoop(
                input_queue,
                output_queue,
                llm=SlowLLM(),
                event_sink=PrintSink(),
                observability_enabled=True,
            )
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

            output_queue.get(timeout=5)
            loop.stop()
            thread.join(timeout=5)

        lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
        events = [json.loads(line) for line in lines]
        types = {event.get("type") for event in events}

        self.assertIn("state_change", types)
        self.assertIn("input", types)
        self.assertIn("output", types)
        self.assertIn("cancel", types)
        self.assertIn("metrics", types)

        for event in events:
            self.assertIn("timestamp", event)
            self.assertIn("state", event)
            self.assertIn("task_id", event)
            self.assertIn("version", event)
            self.assertIn("payload", event)


if __name__ == "__main__":
    unittest.main()
