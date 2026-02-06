import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from field import ConsensusEngine


class TestConsensusEngine(unittest.TestCase):
    def test_range(self):
        engine = ConsensusEngine(strength=0.2)
        bias = engine.compute(
            {"confidence_alignment": 1.0, "orientation_coherence": 0.0},
            "B",
            0.5,
        )
        self.assertGreaterEqual(bias, -0.15)
        self.assertLessEqual(bias, 0.15)

    def test_signs(self):
        engine = ConsensusEngine(strength=0.2)
        bias_b = engine.compute(
            {"confidence_alignment": 1.0, "orientation_coherence": 0.0},
            "B",
            0.5,
        )
        bias_a = engine.compute(
            {"confidence_alignment": 1.0, "orientation_coherence": 0.0},
            "A",
            0.5,
        )
        self.assertGreater(bias_b, 0.0)
        self.assertLess(bias_a, 0.0)

    def test_empty_metrics(self):
        engine = ConsensusEngine()
        self.assertEqual(engine.compute({}, "A", 0.5), 0.0)


if __name__ == "__main__":
    unittest.main()
