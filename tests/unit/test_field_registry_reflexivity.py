import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from field import FieldRegistry, FieldNodeState, FieldResonance, FieldReflexivity


class TestFieldRegistryReflexivity(unittest.TestCase):
    def _make_node(self, timestamp: float, tension: float) -> FieldNodeState:
        return FieldNodeState(
            node_id="node-1",
            timestamp=timestamp,
            orientation={"o": 0.1},
            confidence={"smoothed": 0.5},
            trajectory={"error": tension},
        )

    def test_reflexivity_softens_changes(self):
        registry = FieldRegistry(
            ttl=5.0,
            resonance=FieldResonance(),
            reflexivity=FieldReflexivity(lr=0.05),
        )
        registry.update_node(self._make_node(0.0, 0.2))
        _ = registry.get_state().metrics or {}

        registry.update_node(self._make_node(1.0, 0.8))
        metrics = registry.get_state().metrics or {}
        base_value = 0.8
        adjusted = metrics.get("trajectory_tension")
        self.assertIsNotNone(adjusted)
        self.assertLess(adjusted, base_value)
        self.assertGreaterEqual(adjusted, 0.0)

    def test_disabled_reflexivity_matches_baseline(self):
        baseline = FieldRegistry(ttl=5.0, resonance=FieldResonance())
        baseline.update_node(self._make_node(0.0, 0.2))
        _ = baseline.get_state().metrics or {}
        baseline.update_node(self._make_node(1.0, 0.8))
        baseline_metrics = baseline.get_state().metrics or {}

        registry = FieldRegistry(
            ttl=5.0,
            resonance=FieldResonance(),
            reflexivity=None,
        )
        registry.update_node(self._make_node(0.0, 0.2))
        _ = registry.get_state().metrics or {}
        registry.update_node(self._make_node(1.0, 0.8))
        metrics = registry.get_state().metrics or {}

        self.assertEqual(metrics.get("trajectory_tension"), baseline_metrics.get("trajectory_tension"))


if __name__ == "__main__":
    unittest.main()
