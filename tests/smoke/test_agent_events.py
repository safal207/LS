import io
import json
import queue
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


class DummyLLM:
    def generate_response(self, question: str, cancel_event=None):
        return "ok"

    def format_response(self, response: str) -> str:
        return response


class TestAgentEvents(unittest.TestCase):
    def test_events_emit_to_print_sink(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            loop = AgentLoop(
                output_queue=queue.Queue(),
                llm=DummyLLM(),
                event_sink=PrintSink(),
                observability_enabled=True,
            )
            loop.handle_input("hello")

        lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
        self.assertGreater(len(lines), 0)
        events = [json.loads(line) for line in lines]
        types = {event.get("type") for event in events}

        self.assertIn("input", types)
        self.assertIn("output", types)
        self.assertIn("metrics", types)
        self.assertIn("phase_transition", types)

        for event in events:
            self.assertIn("timestamp", event)
            self.assertIn("state", event)
            self.assertIn("task_id", event)
            self.assertIn("version", event)
            self.assertIn("payload", event)

        input_events = [event for event in events if event.get("type") == "input"]
        self.assertTrue(any("payload" in event for event in input_events))

        metrics_events = [event for event in events if event.get("type") == "metrics"]
        self.assertTrue(metrics_events)
        metrics_payload = metrics_events[-1].get("payload", {})
        self.assertIn("phase_counts", metrics_payload)
        self.assertIn("phase_durations", metrics_payload)
        self.assertIn("phase_transitions", metrics_payload)
        self.assertIn("liminal_transitions", metrics_payload)

    def test_liminal_transition_emits(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            loop = AgentLoop(
                output_queue=queue.Queue(),
                llm=DummyLLM(),
                event_sink=PrintSink(),
                observability_enabled=True,
            )
            loop._emit("input_received", {"text": "hi"}, task_id=1)
            loop._emit("state_change", {"transition_signal": True}, task_id=1)

        events = [json.loads(line) for line in buffer.getvalue().splitlines() if line.strip()]
        types = {event.get("type") for event in events}
        self.assertIn("liminal_transition", types)


if __name__ == "__main__":
    unittest.main()
