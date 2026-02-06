import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from field import FieldDampening


class TestFieldDampening(unittest.TestCase):
    def test_empty_metrics(self):
        damp = FieldDampening()
        self.assertEqual(damp.apply({}), {})

    def test_smoothing(self):
        damp = FieldDampening(alpha=0.5)
        first = damp.apply({"orientation_coherence": 0.2})
        self.assertAlmostEqual(first["orientation_coherence"], 0.2, places=6)
        second = damp.apply({"orientation_coherence": 1.0})
        self.assertGreater(second["orientation_coherence"], 0.2)
        self.assertLess(second["orientation_coherence"], 1.0)

    def test_clamping(self):
        damp = FieldDampening(alpha=1.0)
        high = damp.apply({"trajectory_tension": 5.0})
        low = damp.apply({"trajectory_tension": -3.0})
        self.assertLessEqual(high["trajectory_tension"], 1.0)
        self.assertGreaterEqual(low["trajectory_tension"], 0.0)


if __name__ == "__main__":
    unittest.main()
