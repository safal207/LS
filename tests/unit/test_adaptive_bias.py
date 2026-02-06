import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from coordinator.adaptive_bias import AdaptiveBias


class TestAdaptiveBias(unittest.TestCase):
    def test_bias_combination_is_clamped(self):
        bias = AdaptiveBias()
        orientation_bias = bias.compute_orientation_bias({"tendency": 1.0, "weight": 1.0})
        trajectory_bias = bias.compute_trajectory_bias(1.0)
        combined = bias.combine(orientation_bias, trajectory_bias)
        self.assertGreaterEqual(combined, -0.3)
        self.assertLessEqual(combined, 0.3)

    def test_orientation_bias_uses_weight_and_tendency(self):
        bias = AdaptiveBias()
        value = bias.compute_orientation_bias({"tendency": 0.4, "weight": 0.2})
        self.assertIsInstance(value, float)

    def test_trajectory_bias_handles_none(self):
        bias = AdaptiveBias()
        self.assertEqual(bias.compute_trajectory_bias(None), 0.0)


if __name__ == "__main__":
    unittest.main()
