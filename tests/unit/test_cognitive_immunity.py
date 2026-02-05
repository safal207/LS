import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from orientation import CognitiveImmunity


class TestCognitiveImmunity(unittest.TestCase):
    def test_returns_float_in_range(self):
        engine = CognitiveImmunity()
        score = engine.evaluate({"anomaly_rate": 0.2, "bias_flags": 2, "drift_signals": [0.1, 0.2]})
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


if __name__ == "__main__":
    unittest.main()
