import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from coordinator.confidence_dynamics import ConfidenceDynamics


class TestConfidenceDynamics(unittest.TestCase):
    def test_first_value_passthrough(self):
        dyn = ConfidenceDynamics()
        value = dyn.update(0.8)
        self.assertAlmostEqual(value, 0.8, places=4)

    def test_smoothing_and_clamping(self):
        dyn = ConfidenceDynamics(alpha=0.5, max_delta=0.1)
        v1 = dyn.update(0.0)
        v2 = dyn.update(1.0)
        self.assertLessEqual(v2 - v1, 0.1)


if __name__ == "__main__":
    unittest.main()
