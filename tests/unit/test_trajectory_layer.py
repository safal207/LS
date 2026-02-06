import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from trajectory import TrajectoryLayer


class TestTrajectoryLayer(unittest.TestCase):
    def test_records_decision(self):
        layer = TrajectoryLayer(max_history=2)
        layer.record_decision("A", {"foo": "bar"})
        self.assertEqual(len(layer.history), 1)
        self.assertEqual(layer.history[0].decision, "A")

    def test_records_outcome(self):
        layer = TrajectoryLayer()
        layer.record_decision("A", {})
        layer.record_outcome({"success": False})
        self.assertIsNotNone(layer.history[0].outcome)

    def test_trajectory_error(self):
        layer = TrajectoryLayer()
        layer.record_decision("A", {})
        layer.record_outcome({"success": False})
        layer.record_decision("B", {})
        layer.record_outcome({"success": True})
        self.assertAlmostEqual(layer.compute_trajectory_error(), 0.5, places=4)

    def test_max_history(self):
        layer = TrajectoryLayer(max_history=1)
        layer.record_decision("A", {})
        layer.record_decision("B", {})
        self.assertEqual(len(layer.history), 1)
        self.assertEqual(layer.history[0].decision, "B")


if __name__ == "__main__":
    unittest.main()
