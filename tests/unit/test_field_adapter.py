import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from field import FieldAdapter, FieldRegistry


class TestFieldAdapter(unittest.TestCase):
    def test_publish_and_pull(self):
        registry = FieldRegistry(ttl=10.0)
        adapter = FieldAdapter(node_id="node-1", registry=registry)
        snapshot = {
            "orientation": {"weight": 0.1},
            "confidence": {"raw": 0.5},
            "trajectory": {"error": 0.2},
        }
        adapter.publish_from_ls(snapshot)
        state = adapter.pull_field_state()
        self.assertIn("node-1", state.nodes)
        node = state.nodes["node-1"]
        self.assertIn("weight", node.orientation)

    def test_pull_field_metrics(self):
        registry = FieldRegistry(ttl=10.0)
        adapter = FieldAdapter(node_id="node-1", registry=registry)
        metrics = adapter.pull_field_metrics()
        self.assertEqual(metrics, {})


if __name__ == "__main__":
    unittest.main()
