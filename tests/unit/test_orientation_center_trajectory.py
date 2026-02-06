import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from orientation import OrientationCenter


class TestOrientationCenterTrajectory(unittest.TestCase):
    def test_trajectory_signal_present(self):
        center = OrientationCenter()
        output = center.evaluate(
            history_stats={},
            beliefs=[],
            temporal_metrics={},
            immunity_signals={},
            conviction_inputs={},
            trajectory_error=0.7,
        )
        data = output.to_dict()
        self.assertIn("trajectory_signal", data)
        self.assertAlmostEqual(data["trajectory_signal"], 0.7, places=4)


if __name__ == "__main__":
    unittest.main()
