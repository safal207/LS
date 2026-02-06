import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from coordinator import FieldCoordination


class TestFieldCoordination(unittest.TestCase):
    def test_bias_range(self):
        coord = FieldCoordination(weight=0.15)
        bias = coord.compute({"trajectory_tension": 1.0, "orientation_coherence": 0.0})
        self.assertGreaterEqual(bias, -0.2)
        self.assertLessEqual(bias, 0.2)

    def test_bias_reacts_to_metrics(self):
        coord = FieldCoordination(weight=0.2)
        high_tension = coord.compute({"trajectory_tension": 1.0, "orientation_coherence": 0.0})
        high_coherence = coord.compute({"trajectory_tension": 0.0, "orientation_coherence": 1.0})
        self.assertGreater(high_tension, 0.0)
        self.assertLess(high_coherence, 0.0)

    def test_empty_metrics(self):
        coord = FieldCoordination()
        self.assertEqual(coord.compute({}), 0.0)


if __name__ == "__main__":
    unittest.main()
