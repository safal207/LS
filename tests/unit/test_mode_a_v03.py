import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from modes.mode_a import FastMode


class TestModeAStats(unittest.TestCase):
    def setUp(self):
        self.mode_a = FastMode()

    def test_initial_stats(self):
        stats = self.mode_a.get_stats()
        self.assertEqual(stats["inputs"], 0)
        self.assertEqual(stats["cache_hits"], 0)
        self.assertEqual(stats["cache_misses"], 0)
        self.assertEqual(stats["load_shed"], 0)
        self.assertIn("heuristics", stats)
        self.assertIn("input_length", stats)

    def test_input_length_tracking(self):
        self.mode_a.process("hi")
        stats = self.mode_a.get_stats()
        self.assertEqual(stats["inputs"], 1)
        length = stats["input_length"]
        self.assertEqual(length["count"], 1)
        self.assertEqual(length["min"], 2)
        self.assertEqual(length["max"], 2)
        self.assertEqual(length["avg"], 2.0)
        self.assertEqual(length["buckets"]["0-4"], 1)

    def test_cache_stats(self):
        self.mode_a.process("time")
        self.mode_a.process("time")
        stats = self.mode_a.get_stats()
        self.assertEqual(stats["cache_misses"], 1)
        self.assertEqual(stats["cache_hits"], 1)
        heuristics = stats["heuristics"]
        self.assertEqual(heuristics["temporal_lookup"], 1)

    def test_load_shed_stats(self):
        self.mode_a.process("rev hello", system_load=0.9)
        stats = self.mode_a.get_stats()
        self.assertEqual(stats["load_shed"], 1)
        self.assertEqual(stats["load_shed_by_source"]["string_command"], 1)

    def test_reset_stats(self):
        self.mode_a.process("len hello")
        self.mode_a.reset_stats()
        stats = self.mode_a.get_stats()
        self.assertEqual(stats["inputs"], 0)
        self.assertEqual(stats["cache_hits"], 0)
        self.assertEqual(stats["cache_misses"], 0)
        self.assertEqual(stats["load_shed"], 0)

    def test_stats_copy(self):
        stats = self.mode_a.get_stats()
        stats["inputs"] = 999
        fresh = self.mode_a.get_stats()
        self.assertNotEqual(fresh["inputs"], 999)


if __name__ == "__main__":
    unittest.main()
