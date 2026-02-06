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


class TestCoordinatorTrajectory(unittest.TestCase):
    def test_decide_records_trajectory(self):
        coord = Coordinator()
        result = coord.decide(
            input_data="hello",
            context={},
            telemetry={},
            retrospective={},
        )
        self.assertIn("trajectory_error", result)
        self.assertIn("trajectory_signal", result["orientation"])
        self.assertEqual(len(coord.trajectory.history), 1)

    def test_record_outcome_updates_error(self):
        coord = Coordinator()
        coord.decide(
            input_data="hello",
            context={},
            telemetry={},
            retrospective={},
        )
        coord.record_outcome({"success": False})
        self.assertIsNotNone(coord.last_trajectory_error)
        self.assertGreaterEqual(coord.last_trajectory_error, 0.0)


if __name__ == "__main__":
    unittest.main()
