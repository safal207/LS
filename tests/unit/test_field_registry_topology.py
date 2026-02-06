import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from field import (
    CognitiveMesh,
    CognitiveTopology,
    FieldMorphogenesis,
    FieldNodeState,
    FieldRegistry,
    FieldResonance,
)


class TestFieldRegistryTopology(unittest.TestCase):
    def _build_nodes(self):
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
        return node_a, node_b

    def test_topology_applies_soft_adjustment(self):
        clock = lambda: 1.0
        mesh = CognitiveMesh(lr=0.0)
        mesh.mesh_state.update(
            {
                "coherence_pattern": 1.0,
                "alignment_pattern": 1.0,
                "tension_pattern": 1.0,
            }
        )
        topology = CognitiveTopology(lr=0.1)
        registry_topology = FieldRegistry(
            ttl=5.0,
            clock=clock,
            resonance=FieldResonance(),
            mesh=mesh,
            topology=topology,
        )
        registry_phase23 = FieldRegistry(
            ttl=5.0,
            clock=clock,
            resonance=FieldResonance(),
            mesh=mesh,
        )

        node_a, node_b = self._build_nodes()
        for registry in (registry_topology, registry_phase23):
            registry.update_node(node_a)
            registry.update_node(node_b)

        metrics_phase23 = registry_phase23.get_state().metrics or {}
        metrics_topology = registry_topology.get_state().metrics or {}

        for key in ("orientation_coherence", "confidence_alignment", "trajectory_tension"):
            self.assertGreaterEqual(metrics_topology[key], 0.0)
            self.assertLessEqual(metrics_topology[key], 1.0)
            diff = abs(metrics_topology[key] - metrics_phase23[key])
            self.assertLessEqual(diff, 0.2)

    def test_no_topology_matches_phase23(self):
        clock = lambda: 1.0
        mesh = CognitiveMesh(lr=0.0)
        morphogenesis = FieldMorphogenesis(lr=0.0)
        registry_no_topology = FieldRegistry(
            ttl=5.0,
            clock=clock,
            resonance=FieldResonance(),
            mesh=mesh,
            morphogenesis=morphogenesis,
        )
        registry_phase23 = FieldRegistry(
            ttl=5.0,
            clock=clock,
            resonance=FieldResonance(),
            mesh=mesh,
            morphogenesis=morphogenesis,
        )

        node_a, node_b = self._build_nodes()
        for registry in (registry_no_topology, registry_phase23):
            registry.update_node(node_a)
            registry.update_node(node_b)

        metrics_no_topology = registry_no_topology.get_state().metrics or {}
        metrics_phase23 = registry_phase23.get_state().metrics or {}
        self.assertEqual(metrics_no_topology, metrics_phase23)


if __name__ == "__main__":
    unittest.main()
