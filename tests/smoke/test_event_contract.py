import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from agent.event_schema import build_observability_event


class TestEventContract(unittest.TestCase):
    def test_event_contract_fields(self):
        event = build_observability_event(
            "input_received",
            {"text": "hi"},
            "idle",
            "42",
            timestamp=123.0,
        )
        self.assertIsNotNone(event)
        self.assertEqual(event["type"], "input")
        self.assertEqual(event["timestamp"], 123.0)
        self.assertEqual(event["task_id"], "42")
        self.assertEqual(event["version"], "1.0")
        self.assertEqual(event["state"], "idle")
        self.assertEqual(event["payload"], {"text": "hi"})

    def test_unknown_event_is_ignored(self):
        event = build_observability_event(
            "llm_started",
            {"question": "hi"},
            "thinking",
            "42",
        )
        self.assertIsNone(event)

    def test_phase_transition_event(self):
        event = build_observability_event(
            "phase_transition",
            {"from_phase": "perceive", "to_phase": "interpret"},
            "thinking",
            "99",
            timestamp=456.0,
        )
        self.assertIsNotNone(event)
        self.assertEqual(event["type"], "phase_transition")
        self.assertEqual(event["timestamp"], 456.0)
        self.assertEqual(event["task_id"], "99")


if __name__ == "__main__":
    unittest.main()
