import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from orientation import OrientationFusionLayer, OrientationSignals


class TestFusionLayer(unittest.TestCase):
    def test_first_fuse_returns_raw(self):
        layer = OrientationFusionLayer(smoothing=0.5)
        signals = OrientationSignals(1.0, 0.2, 0.3, 0.4, 0.5)
        fused = layer.fuse(signals)
        self.assertEqual(fused, signals)

    def test_blends_with_previous(self):
        layer = OrientationFusionLayer(smoothing=0.5)
        first = OrientationSignals(1.0, 0.0, 0.0, 0.0, 0.0)
        second = OrientationSignals(0.0, 1.0, 1.0, 1.0, 1.0)
        layer.fuse(first)
        fused = layer.fuse(second)
        self.assertAlmostEqual(fused.diversity_score, 0.5, places=4)
        self.assertAlmostEqual(fused.stability_score, 0.5, places=4)
        self.assertAlmostEqual(fused.contradiction_rate, 0.5, places=4)
        self.assertAlmostEqual(fused.drift_pressure, 0.5, places=4)
        self.assertAlmostEqual(fused.confidence_budget, 0.5, places=4)


if __name__ == "__main__":
    unittest.main()
