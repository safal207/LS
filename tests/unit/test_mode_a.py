import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from modes.mode_a import ModeA


class TestModeA(unittest.TestCase):
    def setUp(self):
        self.mode = ModeA()

    def test_execute_returns_fast_response(self):
        result = self.mode.execute("echo hello", context={})
        self.assertEqual(result["mode"], "A")
        self.assertEqual(result["answer"], "hello")
        self.assertIn("timestamp", result)

    def test_no_context_mutation(self):
        context = {"key": "value"}
        _ = self.mode.execute("pi", context=context)
        self.assertEqual(context, {"key": "value"})

    def test_high_load_still_fast(self):
        result = self.mode.execute("upper hello", context={}, system_load=0.95)
        self.assertEqual(result["answer"], "HELLO")


if __name__ == "__main__":
    unittest.main()
