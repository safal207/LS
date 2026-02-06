import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from field import CognitiveMesh, FieldNodeState, FieldRegistry, FieldResonance


class TestFieldRegistryMesh(unittest.TestCase):
    def test_mesh_applies_soft_correction(self):
        clock = lambda: 1.0
        registry_raw = FieldRegistry(ttl=5.0, clock=clock, resonance=FieldResonance())
        mesh = CognitiveMesh(lr=0.0)
        mesh.mesh_state.update(
            {
                "coherence_pattern": 1.0,
                "alignment_pattern": 1.0,
                "tension_pattern": 1.0,
            }
        )
        registry_mesh = FieldRegistry(
            ttl=5.0, clock=clock, resonance=FieldResonance(), mesh=mesh
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

        for registry in (registry_raw, registry_mesh):
            registry.update_node(node_a)
            registry.update_node(node_b)

        metrics_raw = registry_raw.get_state().metrics or {}
        metrics_mesh = registry_mesh.get_state().metrics or {}

        self.assertGreater(metrics_mesh["orientation_coherence"], metrics_raw["orientation_coherence"])
        self.assertGreater(metrics_mesh["confidence_alignment"], metrics_raw["confidence_alignment"])
        self.assertLessEqual(
            metrics_mesh["orientation_coherence"] - metrics_raw["orientation_coherence"], 0.5
        )
        self.assertLessEqual(
            metrics_mesh["confidence_alignment"] - metrics_raw["confidence_alignment"], 0.5
        )
        for key in ("orientation_coherence", "confidence_alignment", "trajectory_tension"):
            self.assertGreaterEqual(metrics_mesh[key], 0.0)
            self.assertLessEqual(metrics_mesh[key], 1.0)


if __name__ == "__main__":
    unittest.main()
