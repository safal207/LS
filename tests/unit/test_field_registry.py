import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from field import FieldRegistry, FieldNodeState, FieldResonance


class TestFieldRegistry(unittest.TestCase):
    def test_registry_add_and_get(self):
        now = [0.0]
        registry = FieldRegistry(ttl=5.0, clock=lambda: now[0])
        node = FieldNodeState(
            node_id="node-1",
            timestamp=now[0],
            orientation={"phase": 1.0},
            confidence={"raw": 0.5},
            trajectory={"error": 0.1},
        )
        registry.update_node(node)
        state = registry.get_state()
        self.assertIn("node-1", state.nodes)

    def test_registry_ttl_prunes(self):
        now = [0.0]
        registry = FieldRegistry(ttl=1.0, clock=lambda: now[0])
        node = FieldNodeState(
            node_id="node-1",
            timestamp=now[0],
            orientation={},
            confidence={},
            trajectory={},
        )
        registry.update_node(node)
        now[0] = 2.0
        state = registry.get_state()
        self.assertNotIn("node-1", state.nodes)

    def test_registry_metrics_when_resonance_enabled(self):
        registry = FieldRegistry(ttl=5.0, resonance=FieldResonance())
        node = FieldNodeState(
            node_id="node-1",
            timestamp=0.0,
            orientation={"o": 0.1},
            confidence={"smoothed": 0.4},
            trajectory={"error": 0.2},
        )
        registry.update_node(node)
        state = registry.get_state()
        self.assertIsNotNone(state.metrics)
        self.assertIn("orientation_coherence", state.metrics)


if __name__ == "__main__":
    unittest.main()
