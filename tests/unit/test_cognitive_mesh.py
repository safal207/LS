import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from field import CognitiveMesh


class TestCognitiveMesh(unittest.TestCase):
    def test_empty_metrics_no_change(self):
        mesh = CognitiveMesh()
        state = dict(mesh.mesh_state)
        self.assertEqual(mesh.update({}), state)
        self.assertEqual(mesh.mesh_state, state)

    def test_mesh_state_stays_in_range(self):
        mesh = CognitiveMesh(lr=1.0)
        mesh.update(
            {
                "orientation_coherence": 2.0,
                "confidence_alignment": -1.0,
                "trajectory_tension": 4.0,
            }
        )
        for value in mesh.mesh_state.values():
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)

    def test_mesh_state_changes_slowly(self):
        mesh = CognitiveMesh(lr=0.1)
        first = mesh.update(
            {
                "orientation_coherence": 1.0,
                "confidence_alignment": 1.0,
                "trajectory_tension": 1.0,
            }
        )
        second = mesh.update(
            {
                "orientation_coherence": 1.0,
                "confidence_alignment": 1.0,
                "trajectory_tension": 1.0,
            }
        )
        self.assertGreater(second["coherence_pattern"], first["coherence_pattern"])
        self.assertLess(second["coherence_pattern"], 1.0)

    def test_stable_patterns_reinforced(self):
        mesh = CognitiveMesh(lr=0.2)
        for _ in range(5):
            mesh.update(
                {
                    "orientation_coherence": 1.0,
                    "confidence_alignment": 0.9,
                    "trajectory_tension": 0.2,
                }
            )
        self.assertGreater(mesh.mesh_state["coherence_pattern"], 0.5)
        self.assertGreater(mesh.mesh_state["alignment_pattern"], 0.4)
        self.assertLess(mesh.mesh_state["tension_pattern"], 0.5)


if __name__ == "__main__":
    unittest.main()
