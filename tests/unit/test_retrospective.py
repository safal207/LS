import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from retrospective import Retrospective


class TestRetrospective(unittest.TestCase):
    def setUp(self):
        self.retrospective = Retrospective()

    def _sample_stats(self):
        return {
            "inputs": 2,
            "cache_hits": 1,
            "cache_misses": 1,
            "load_shed": 1,
            "load_shed_by_source": {
                "string_command": 1,
                "math": 0,
            },
            "heuristics": {
                "temporal_lookup": 1,
                "math": 0,
                "string_command": 1,
                "mini_nlu": 0,
                "echo": 0,
            },
            "input_length": {
                "count": 2,
                "min": 2,
                "max": 5,
                "total": 7,
                "avg": 3.5,
                "buckets": {
                    "0-4": 1,
                    "5-10": 1,
                    "11-50": 0,
                    "51-100": 0,
                    "101+": 0,
                },
            },
        }

    def test_snapshot_stores_copy(self):
        stats = self._sample_stats()
        self.retrospective.snapshot(stats)
        stats["cache_hits"] = 999
        summary = self.retrospective.summarize()
        self.assertEqual(summary["cache"]["hits"], 1)

    def test_summarize_aggregates(self):
        stats1 = self._sample_stats()
        stats2 = self._sample_stats()
        stats2["cache_hits"] = 2
        stats2["cache_misses"] = 0
        stats2["load_shed"] = 0
        stats2["heuristics"]["echo"] = 1
        stats2["input_length"]["min"] = 1
        stats2["input_length"]["max"] = 10
        stats2["input_length"]["total"] = 11
        stats2["input_length"]["count"] = 3
        stats2["input_length"]["buckets"]["0-4"] = 2
        stats2["input_length"]["buckets"]["5-10"] = 1

        self.retrospective.snapshot(stats1)
        self.retrospective.snapshot(stats2)

        summary = self.retrospective.summarize()
        self.assertEqual(summary["total_snapshots"], 2)
        self.assertEqual(summary["cache"]["hits"], 3)
        self.assertEqual(summary["cache"]["misses"], 1)
        self.assertEqual(summary["load"]["load_shed"], 1)
        self.assertEqual(summary["heuristics_usage"]["echo"], 1)
        self.assertEqual(summary["input"]["min"], 1)
        self.assertEqual(summary["input"]["max"], 10)
        self.assertEqual(summary["input"]["count"], 5)
        self.assertEqual(summary["input"]["buckets"]["0-4"], 3)
        insights = summary["cache_insights"]
        self.assertAlmostEqual(insights["repeat_rate"], 0.75, places=2)
        self.assertAlmostEqual(insights["hit_ratio"], 0.75, places=2)
        self.assertEqual(insights["load_shed_saved"], 0)
        self.assertIn("cache hit rate above 50%", insights["reasons"])
        self.assertIn("cache mitigates load-shed events", insights["reasons"])
        self.assertIn("temporal lookups frequently requested", insights["reasons"])

    def test_reset_clears_history(self):
        self.retrospective.snapshot(self._sample_stats())
        self.retrospective.reset()
        summary = self.retrospective.summarize()
        self.assertEqual(summary["total_snapshots"], 0)
        self.assertEqual(summary["cache"]["total"], 0)


if __name__ == "__main__":
    unittest.main()
