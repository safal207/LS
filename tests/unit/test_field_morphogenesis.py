import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from field import FieldMorphogenesis


class TestFieldMorphogenesis(unittest.TestCase):
    def test_empty_metrics_no_change(self):
        morph = FieldMorphogenesis()
        state = dict(morph.morphology)
        self.assertEqual(morph.update({"coherence_pattern": 1.0}, {}), state)

    def test_morphology_stays_in_range(self):
        morph = FieldMorphogenesis(lr=0.5)
        for _ in range(10):
            state = morph.update(
                {
                    "coherence_pattern": 0.0,
                    "alignment_pattern": 0.0,
                    "tension_pattern": 0.0,
                },
                {
                    "orientation_coherence": 0.0,
                    "confidence_alignment": 0.0,
                    "trajectory_tension": 0.0,
                },
            )
        for value in state.values():
            self.assertGreaterEqual(value, 0.5)
            self.assertLessEqual(value, 1.5)

    def test_morphology_changes_slowly(self):
        morph = FieldMorphogenesis(lr=0.1)
        state = morph.update(
            {
                "coherence_pattern": 0.0,
                "alignment_pattern": 0.0,
                "tension_pattern": 0.0,
            },
            {
                "orientation_coherence": 0.0,
                "confidence_alignment": 0.0,
                "trajectory_tension": 0.0,
            },
        )
        self.assertGreater(state["coherence_scale"], 0.8)

    def test_mesh_influence(self):
        morph_low = FieldMorphogenesis(lr=0.5)
        morph_high = FieldMorphogenesis(lr=0.5)

        state_low = morph_low.update(
            {
                "coherence_pattern": 0.0,
                "alignment_pattern": 0.0,
                "tension_pattern": 0.0,
            },
            {
                "orientation_coherence": 0.2,
                "confidence_alignment": 0.2,
                "trajectory_tension": 0.2,
            },
        )
        state_high = morph_high.update(
            {
                "coherence_pattern": 1.0,
                "alignment_pattern": 1.0,
                "tension_pattern": 1.0,
            },
            {
                "orientation_coherence": 0.2,
                "confidence_alignment": 0.2,
                "trajectory_tension": 0.2,
            },
        )
        self.assertGreater(state_high["coherence_scale"], state_low["coherence_scale"])
        self.assertGreater(state_high["alignment_scale"], state_low["alignment_scale"])


if __name__ == "__main__":
    unittest.main()
