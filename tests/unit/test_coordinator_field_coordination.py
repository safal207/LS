import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from coordinator import Coordinator
from field import FieldAdapter, FieldRegistry, FieldResonance, FieldNodeState


class TestCoordinatorFieldCoordination(unittest.TestCase):
    def test_coordination_bias_in_payload(self):
        registry = FieldRegistry(ttl=10.0, resonance=FieldResonance())
        adapter = FieldAdapter(node_id="node-1", registry=registry)
        registry.update_node(
            FieldNodeState(
                node_id="node-2",
                timestamp=0.0,
                orientation={"o": 0.0},
                confidence={"smoothed": 0.5},
                trajectory={"error": 0.9},
            )
        )
        coord = Coordinator()
        coord.field_adapter = adapter
        result = coord.decide("Hi", context={}, system_load=0.0)
        self.assertIn("coordination_bias", result)
        self.assertEqual(result["mode"], "A")
        self.assertGreaterEqual(result["coordination_bias"], -0.2)
        self.assertLessEqual(result["coordination_bias"], 0.2)

    def test_empty_field_bias_is_zero(self):
        registry = FieldRegistry(ttl=10.0)
        adapter = FieldAdapter(node_id="node-1", registry=registry)
        coord = Coordinator()
        coord.field_adapter = adapter
        result = coord.decide("Hi", context={}, system_load=0.0)
        self.assertEqual(result["coordination_bias"], 0.0)


if __name__ == "__main__":
    unittest.main()
