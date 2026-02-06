import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from field import FieldEvolution


class TestFieldEvolution(unittest.TestCase):
    def test_empty_metrics(self):
        evo = FieldEvolution()
        state = dict(evo.state)
        self.assertEqual(evo.update({}), state)

    def test_weights_stay_in_range(self):
        evo = FieldEvolution(lr=0.5)
        for _ in range(10):
            weights = evo.update(
                {
                    "orientation_coherence": 1.0,
                    "confidence_alignment": 0.0,
                    "trajectory_tension": 1.0,
                }
            )
        for value in weights.values():
            self.assertGreaterEqual(value, 0.5)
            self.assertLessEqual(value, 2.0)

    def test_weights_change_slowly(self):
        evo = FieldEvolution(lr=0.05)
        weights1 = evo.update(
            {
                "orientation_coherence": 1.0,
                "confidence_alignment": 1.0,
                "trajectory_tension": 1.0,
            }
        )
        weights2 = evo.update(
            {
                "orientation_coherence": 1.0,
                "confidence_alignment": 1.0,
                "trajectory_tension": 1.0,
            }
        )
        self.assertGreater(weights2["coherence_weight"], weights1["coherence_weight"])


if __name__ == "__main__":
    unittest.main()
