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

    def test_cache_hit(self):
        first = self.mode.execute("pi", context={})
        second = self.mode.execute("pi", context={})
        self.assertEqual(first["answer"], "3.14159")
        self.assertEqual(second["source"], "cache")

    def test_len_and_rev(self):
        length = self.mode.execute("len hello", context={})
        reverse = self.mode.execute("rev hello", context={})
        self.assertEqual(length["answer"], "5")
        self.assertEqual(reverse["answer"], "olleh")

    def test_greeting_and_thanks(self):
        greeting = self.mode.execute("hi", context={})
        thanks = self.mode.execute("thanks", context={})
        self.assertEqual(greeting["answer"], "hello")
        self.assertEqual(thanks["answer"], "you are welcome")

    def test_numeric_echo(self):
        number = self.mode.execute("123.45", context={})
        self.assertEqual(number["answer"], "123.45")

    def test_no_context_mutation(self):
        context = {"key": "value"}
        _ = self.mode.execute("pi", context=context)
        self.assertEqual(context, {"key": "value"})

    def test_high_load_still_fast(self):
        result = self.mode.execute("upper hello", context={}, system_load=0.95)
        self.assertEqual(result["answer"], "upper hello")


if __name__ == "__main__":
    unittest.main()
