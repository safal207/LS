import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from orientation import OrientationCenter, RhythmEngine, RhythmInputs


class TestRhythmEngine(unittest.TestCase):
    def test_inhale_when_chaos_greater(self):
        engine = RhythmEngine(hold_epsilon=0.1)
        inputs = RhythmInputs(
            diversity_score=1.0,
            stability_score=0.1,
            contradiction_rate=0.6,
            drift_pressure=0.5,
            confidence_budget=0.0,
        )
        result = engine.evaluate(inputs)
        self.assertEqual(result["rhythm_phase"], "inhale")

    def test_exhale_when_harmony_greater(self):
        engine = RhythmEngine(hold_epsilon=0.1)
        inputs = RhythmInputs(
            diversity_score=0.1,
            stability_score=1.0,
            contradiction_rate=0.1,
            drift_pressure=0.1,
            confidence_budget=0.8,
        )
        result = engine.evaluate(inputs)
        self.assertEqual(result["rhythm_phase"], "exhale")

    def test_hold_within_threshold(self):
        engine = RhythmEngine(hold_epsilon=0.2)
        inputs = RhythmInputs(
            diversity_score=1.0,
            stability_score=1.0,
            contradiction_rate=0.0,
            drift_pressure=0.0,
            confidence_budget=0.0,
        )
        result = engine.evaluate(inputs)
        self.assertEqual(result["rhythm_phase"], "hold")


class TestOrientationCenter(unittest.TestCase):
    def test_orientation_output(self):
        center = OrientationCenter(hold_epsilon=0.1)
        inputs = RhythmInputs(
            diversity_score=0.2,
            stability_score=0.2,
            contradiction_rate=0.2,
            drift_pressure=0.2,
            confidence_budget=0.2,
        )
        output = center.evaluate(inputs)
        self.assertIn(output.rhythm_phase, ["inhale", "hold", "exhale"])
        self.assertIsInstance(output.chaos_score, float)
        self.assertIsInstance(output.harmony_score, float)
        self.assertIsInstance(output.delta, float)


if __name__ == "__main__":
    unittest.main()
