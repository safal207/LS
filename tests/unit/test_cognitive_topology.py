import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from field import CognitiveTopology


class TestCognitiveTopology(unittest.TestCase):
    def test_edge_weights_are_clamped(self):
        topology = CognitiveTopology(lr=0.5)
        edges = topology.update(
            {
                "orientation_coherence": 1.0,
                "confidence_alignment": 1.0,
                "trajectory_tension": 0.0,
            },
            {
                "coherence_pattern": 1.0,
                "alignment_pattern": 1.0,
                "tension_pattern": 0.0,
            },
        )
        for weight in edges.values():
            self.assertGreaterEqual(weight, -1.0)
            self.assertLessEqual(weight, 1.0)

    def test_edges_are_stored_symmetrically(self):
        topology = CognitiveTopology(lr=0.2)
        edges = topology.update(
            {
                "orientation_coherence": 0.9,
                "confidence_alignment": 0.1,
                "trajectory_tension": 0.4,
            },
            {
                "coherence_pattern": 0.4,
                "alignment_pattern": 0.2,
                "tension_pattern": 0.1,
            },
        )
        for key in edges.keys():
            self.assertEqual(tuple(sorted(key)), key)

    def test_apply_influences_metrics(self):
        topology = CognitiveTopology(lr=0.1)
        topology.edges[("confidence_alignment", "orientation_coherence")] = 0.2
        metrics = {
            "orientation_coherence": 0.9,
            "confidence_alignment": 0.1,
            "trajectory_tension": 0.5,
        }
        adjusted = topology.apply(metrics)
        self.assertNotEqual(adjusted["orientation_coherence"], metrics["orientation_coherence"])
        self.assertNotEqual(adjusted["confidence_alignment"], metrics["confidence_alignment"])

    def test_apply_returns_original_metrics_without_edges(self):
        topology = CognitiveTopology(lr=0.1)
        metrics = {
            "orientation_coherence": 0.7,
            "confidence_alignment": 0.4,
        }
        self.assertEqual(topology.apply(metrics), metrics)


if __name__ == "__main__":
    unittest.main()
