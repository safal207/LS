import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from field import FieldResonance, FieldState, FieldNodeState


class TestFieldResonance(unittest.TestCase):
    def test_empty_field(self):
        resonance = FieldResonance()
        metrics = resonance.compute(FieldState(nodes={}))
        self.assertEqual(metrics["orientation_coherence"], 0.0)
        self.assertEqual(metrics["confidence_alignment"], 0.0)
        self.assertEqual(metrics["trajectory_tension"], 0.0)

    def test_metrics_range(self):
        resonance = FieldResonance()
        nodes = {
            "a": FieldNodeState(
                node_id="a",
                timestamp=0.0,
                orientation={"x": 0.1},
                confidence={"smoothed": 0.2},
                trajectory={"error": 0.1},
            ),
            "b": FieldNodeState(
                node_id="b",
                timestamp=0.0,
                orientation={"x": 0.9},
                confidence={"smoothed": 0.8},
                trajectory={"error": 0.9},
            ),
        }
        metrics = resonance.compute(FieldState(nodes=nodes))
        for value in metrics.values():
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)


if __name__ == "__main__":
    unittest.main()
