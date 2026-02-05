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


class TestCoordinatorOrientation(unittest.TestCase):
    def test_decide_includes_orientation(self):
        coord = Coordinator()
        result = coord.decide(
            input_data="hello",
            context={},
            telemetry={"diversity": 1.0},
            retrospective={"stability": 0.5},
        )
        self.assertIn("mode", result)
        self.assertIn("orientation", result)
        orientation = result["orientation"]
        self.assertIn(orientation["rhythm_phase"], ["inhale", "hold", "exhale"])
        self.assertIn("weight", orientation)
        self.assertIn("tendency", orientation)
        self.assertIsInstance(orientation["weight"], float)
        self.assertIsInstance(orientation["tendency"], float)


if __name__ == "__main__":
    unittest.main()
