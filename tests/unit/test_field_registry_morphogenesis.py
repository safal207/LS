import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from field import CognitiveMesh, FieldMorphogenesis, FieldNodeState, FieldRegistry, FieldResonance


class TestFieldRegistryMorphogenesis(unittest.TestCase):
    def test_morphology_applies_scaling(self):
        clock = lambda: 1.0
        mesh = CognitiveMesh(lr=0.0)
        mesh.mesh_state.update(
            {
                "coherence_pattern": 1.0,
                "alignment_pattern": 1.0,
                "tension_pattern": 0.0,
            }
        )
        morph = FieldMorphogenesis(lr=1.0)
        registry = FieldRegistry(
            ttl=5.0,
            clock=clock,
            resonance=FieldResonance(),
            mesh=mesh,
            morphogenesis=morph,
        )

        node_a = FieldNodeState(
            node_id="node-a",
            timestamp=0.0,
            orientation={"o": 0.0},
            confidence={"smoothed": 0.0},
            trajectory={"error": 0.0},
        )
        node_b = FieldNodeState(
            node_id="node-b",
            timestamp=0.0,
            orientation={"o": 1.0},
            confidence={"smoothed": 1.0},
            trajectory={"error": 1.0},
        )

        for node in (node_a, node_b):
            registry.update_node(node)

        base_registry = FieldRegistry(
            ttl=5.0,
            clock=clock,
            resonance=FieldResonance(),
            mesh=mesh,
        )
        for node in (node_a, node_b):
            base_registry.update_node(node)

        metrics_mesh = base_registry.get_state().metrics or {}
        metrics_morph = registry.get_state().metrics or {}

        for key in ("orientation_coherence", "confidence_alignment", "trajectory_tension"):
            self.assertGreaterEqual(metrics_morph[key], 0.0)
            self.assertLessEqual(metrics_morph[key], 1.0)
            self.assertLess(metrics_morph[key], metrics_mesh[key])
            self.assertLessEqual(metrics_mesh[key] - metrics_morph[key], 0.5)


if __name__ == "__main__":
    unittest.main()
