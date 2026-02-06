import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from field import FieldReflexivity


class TestFieldReflexivity(unittest.TestCase):
    def test_trend_and_adjustment(self):
        reflex = FieldReflexivity(lr=0.1)
        first = reflex.update({"orientation_coherence": 0.2})
        self.assertEqual(first["orientation_coherence"], 0.0)

        second = reflex.update({"orientation_coherence": 0.5})
        self.assertAlmostEqual(second["orientation_coherence"], -0.03, places=6)
        self.assertAlmostEqual(reflex.trend["orientation_coherence"], 0.3, places=6)

    def test_zero_trend_no_adjustment(self):
        reflex = FieldReflexivity(lr=0.2)
        reflex.update({"confidence_alignment": 0.4})
        second = reflex.update({"confidence_alignment": 0.4})
        self.assertEqual(second["confidence_alignment"], 0.0)

    def test_adjustment_clamping(self):
        reflex = FieldReflexivity(lr=1.0)
        reflex.update({"trajectory_tension": 0.0})
        second = reflex.update({"trajectory_tension": 2.0})
        self.assertEqual(second["trajectory_tension"], -0.1)


if __name__ == "__main__":
    unittest.main()
