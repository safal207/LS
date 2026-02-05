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


class TestOrientationCenterSignals(unittest.TestCase):
    def test_evaluate_returns_all_fields(self):
        center = OrientationCenter()
        output = center.evaluate(
            history_stats={"unique_paths": 2, "total_paths": 5},
            beliefs=[{"age": 10, "support": 0.5}],
            temporal_metrics={"short_term_trend": 0.2, "long_term_trend": 0.5},
            immunity_signals={"anomaly_rate": 0.1, "bias_flags": 1},
            conviction_inputs={"support_level": 0.5, "conflict_level": 0.1},
        )

        data = output.to_dict()
        self.assertIn(data["rhythm_phase"], ["inhale", "hold", "exhale"])
        self.assertIsInstance(data["diversity_score"], float)
        self.assertIsInstance(data["stability_score"], float)
        self.assertIsInstance(data["contradiction_rate"], float)
        self.assertIsInstance(data["drift_pressure"], float)
        self.assertIsInstance(data["confidence_budget"], float)


if __name__ == "__main__":
    unittest.main()
