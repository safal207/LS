import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from orientation import MetabolicDiversity


class TestMetabolicDiversity(unittest.TestCase):
    def test_returns_float_in_range(self):
        engine = MetabolicDiversity()
        score = engine.evaluate({"unique_paths": 5, "total_paths": 10})
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


if __name__ == "__main__":
    unittest.main()
