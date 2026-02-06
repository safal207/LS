import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from coordinator import Coordinator


class TestCoordinatorAdaptive(unittest.TestCase):
    def test_adaptive_bias_included(self):
        coord = Coordinator()
        result = coord.decide(
            input_data="hello",
            context={},
            telemetry={"diversity": 1.0},
            retrospective={"stability": 0.5},
        )
        orientation = result["orientation"]
        self.assertIn("orientation_bias", orientation)
        self.assertIn("trajectory_bias", orientation)
        self.assertIn("adaptive_bias", orientation)
        self.assertIsInstance(orientation["adaptive_bias"], float)
        self.assertGreaterEqual(result["confidence"], 0.0)
        self.assertLessEqual(result["confidence"], 1.0)


if __name__ == "__main__":
    unittest.main()
