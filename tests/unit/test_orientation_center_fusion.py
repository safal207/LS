import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from orientation import OrientationCenter, OrientationFusionLayer


class TestOrientationCenterFusion(unittest.TestCase):
    def test_center_uses_fusion_layer(self):
        fusion = OrientationFusionLayer(smoothing=1.0)
        center = OrientationCenter(fusion_layer=fusion)

        first = center.evaluate(
            history_stats={"unique_paths": 1, "total_paths": 1},
            beliefs=[{"age": 10, "support": 1.0}],
            temporal_metrics={"short_term_trend": 0.0, "long_term_trend": 0.0},
            immunity_signals={"anomaly_rate": 0.0, "bias_flags": 0},
            conviction_inputs={"support_level": 1.0, "conflict_level": 0.0},
        )

        second = center.evaluate(
            history_stats={"unique_paths": 0, "total_paths": 10},
            beliefs=[{"age": 0, "support": 0.0}],
            temporal_metrics={"short_term_trend": 1.0, "long_term_trend": 0.0},
            immunity_signals={"anomaly_rate": 1.0, "bias_flags": 10},
            conviction_inputs={"support_level": 0.0, "conflict_level": 1.0},
        )

        self.assertEqual(second.diversity_score, first.diversity_score)
        self.assertEqual(second.stability_score, first.stability_score)


if __name__ == "__main__":
    unittest.main()
