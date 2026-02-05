import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from orientation import ConvictionRegulator


class TestConvictionRegulator(unittest.TestCase):
    def test_returns_float_in_range(self):
        engine = ConvictionRegulator()
        score = engine.evaluate({
            "support_level": 0.7,
            "diversity_of_evidence": 0.6,
            "conflict_level": 0.2,
            "belief_age": 40,
        })
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


if __name__ == "__main__":
    unittest.main()
