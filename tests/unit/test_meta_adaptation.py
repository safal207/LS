import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from coordinator.confidence_dynamics import ConfidenceDynamics
from coordinator.meta_adaptation import MetaAdaptationLayer


class TestMetaAdaptation(unittest.TestCase):
    def test_updates_state(self):
        meta = MetaAdaptationLayer()
        meta.update_metrics(trajectory_error=0.8, confidence=0.3)
        self.assertGreaterEqual(meta.state.updates, 1)
        self.assertGreater(meta.state.avg_trajectory_error, 0.0)

    def test_adapts_confidence_dynamics(self):
        meta = MetaAdaptationLayer()
        dyn = ConfidenceDynamics(alpha=0.5, max_delta=0.2)
        for _ in range(20):
            meta.update_metrics(trajectory_error=0.9, confidence=0.3)
        meta.adapt_confidence_dynamics(dyn)
        self.assertLessEqual(dyn.max_delta, 0.2)
        self.assertGreaterEqual(dyn.alpha, 0.5)


if __name__ == "__main__":
    unittest.main()
