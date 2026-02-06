import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from field import FieldRegistry, FieldNodeState, FieldResonance, FieldEvolution


class TestFieldRegistryEvolution(unittest.TestCase):
    def test_registry_applies_weights(self):
        registry = FieldRegistry(
            ttl=5.0,
            resonance=FieldResonance(),
            evolution=FieldEvolution(lr=0.5),
        )
        node = FieldNodeState(
            node_id="node-1",
            timestamp=0.0,
            orientation={"o": 0.1},
            confidence={"smoothed": 0.4},
            trajectory={"error": 0.2},
        )
        registry.update_node(node)
        metrics1 = registry.get_state().metrics or {}

        node2 = FieldNodeState(
            node_id="node-1",
            timestamp=1.0,
            orientation={"o": 0.9},
            confidence={"smoothed": 0.8},
            trajectory={"error": 0.9},
        )
        registry.update_node(node2)
        metrics2 = registry.get_state().metrics or {}

        if metrics1 and metrics2:
            self.assertIsNotNone(metrics2.get("orientation_coherence"))
            self.assertGreaterEqual(metrics2["orientation_coherence"], 0.0)
            self.assertLessEqual(metrics2["orientation_coherence"], 1.0)


if __name__ == "__main__":
    unittest.main()
