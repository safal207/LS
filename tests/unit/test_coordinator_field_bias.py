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
from field import FieldAdapter, FieldRegistry, FieldResonance, FieldBias


class TestCoordinatorFieldBias(unittest.TestCase):
    def test_field_bias_included_without_mode_change(self):
        coord = Coordinator()
        registry = FieldRegistry(ttl=10.0, resonance=FieldResonance())
        coord.field_adapter = FieldAdapter(node_id="node-1", registry=registry)
        coord.field_bias = FieldBias()

        result = coord.decide("Hi", context={}, system_load=0.0)

        self.assertEqual(result["mode"], "A")
        self.assertIn("field_bias", result)
        self.assertIn("orientation_bias", result["field_bias"])
        self.assertIn("confidence_bias", result["field_bias"])
        self.assertIn("trajectory_bias", result["field_bias"])


if __name__ == "__main__":
    unittest.main()
