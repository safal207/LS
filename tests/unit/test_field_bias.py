import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from field import FieldBias


class TestFieldBias(unittest.TestCase):
    def test_empty_metrics(self):
        bias = FieldBias()
        values = bias.compute_bias({})
        self.assertEqual(values["orientation_bias"], 0.0)
        self.assertEqual(values["confidence_bias"], 0.0)
        self.assertEqual(values["trajectory_bias"], 0.0)

    def test_bias_range(self):
        bias = FieldBias()
        values = bias.compute_bias(
            {
                "orientation_coherence": 0.1,
                "confidence_alignment": 0.2,
                "trajectory_tension": 0.9,
            }
        )
        for value in values.values():
            self.assertGreaterEqual(value, -0.2)
            self.assertLessEqual(value, 0.2)


if __name__ == "__main__":
    unittest.main()
