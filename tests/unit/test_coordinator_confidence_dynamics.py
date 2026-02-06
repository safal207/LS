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


class TestCoordinatorConfidenceDynamics(unittest.TestCase):
    def test_confidence_dynamics_fields(self):
        coord = Coordinator()
        result = coord.decide(
            input_data="hello",
            context={},
            telemetry={"diversity": 1.0},
            retrospective={"stability": 0.5},
        )
        self.assertIn("confidence_raw", result)
        self.assertIn("confidence_smoothed", result)
        self.assertGreaterEqual(result["confidence_smoothed"], 0.0)
        self.assertLessEqual(result["confidence_smoothed"], 1.0)


if __name__ == "__main__":
    unittest.main()
