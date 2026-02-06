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
from coordinator.meta_hygiene import MetaHygiene


class TestMetaHygiene(unittest.TestCase):
    def test_clamps_parameters(self):
        hygiene = MetaHygiene(alpha_bounds=(0.2, 0.8), max_delta_bounds=(0.1, 0.3))
        dynamics = ConfidenceDynamics(alpha=0.95, max_delta=0.5)
        hygiene.correct_confidence_dynamics(dynamics)
        self.assertGreaterEqual(dynamics.alpha, 0.2)
        self.assertLessEqual(dynamics.alpha, 0.8)
        self.assertGreaterEqual(dynamics.max_delta, 0.1)
        self.assertLessEqual(dynamics.max_delta, 0.3)

    def test_resets_after_spikes(self):
        hygiene = MetaHygiene(
            alpha_spike_threshold=0.01,
            delta_spike_threshold=0.01,
            spike_limit=2,
            baseline_alpha=0.5,
            baseline_max_delta=0.2,
        )
        dynamics = ConfidenceDynamics(alpha=0.9, max_delta=0.4)
        hygiene.correct_confidence_dynamics(dynamics)
        dynamics.alpha = 0.1
        dynamics.max_delta = 0.05
        hygiene.correct_confidence_dynamics(dynamics)
        self.assertEqual(dynamics.alpha, 0.5)
        self.assertEqual(dynamics.max_delta, 0.2)


if __name__ == "__main__":
    unittest.main()
