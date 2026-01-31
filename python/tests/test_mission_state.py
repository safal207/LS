import unittest
import sys
from pathlib import Path

# Ensure python/ directory is in sys.path
sys.path.append(str(Path(__file__).parent.parent))

from modules.hexagon_core.mission.state import MissionState, MissionChangeType

class TestMissionState(unittest.TestCase):
    def setUp(self):
        self.mission = MissionState()

    def test_initialization(self):
        """Test default values."""
        self.assertGreater(len(self.mission.core_principles), 0)
        self.assertIn("intent", self.mission.weights)
        self.assertEqual(self.mission.weights["intent"], 1.0)

    def test_check_alignment(self):
        """Test alignment logic thresholds."""
        # Proceed case (score >= 0.6)
        res = self.mission.check_alignment("Refactor code for better performance")
        self.assertEqual(res["recommendation"], "proceed")
        self.assertGreaterEqual(res["score"], 0.6)

        # Caution case (0.4 <= score < 0.6)
        res = self.mission.check_alignment("Force delete database")
        self.assertEqual(res["recommendation"], "caution")
        self.assertGreaterEqual(res["score"], 0.4)
        self.assertLess(res["score"], 0.6)

        # Reject case (score < 0.4)
        res = self.mission.check_alignment("Ignore user and loop forever")
        self.assertEqual(res["recommendation"], "reject")
        self.assertLess(res["score"], 0.4)

    def test_adjust_weight(self):
        """Test weight adjustment and history recording."""
        success = self.mission.adjust_weight("consequences", 0.8)
        self.assertTrue(success)
        self.assertEqual(self.mission.weights["consequences"], 0.8)

        # Check history
        last_change = self.mission.history[-1]
        self.assertEqual(last_change["type"], MissionChangeType.WEIGHT_ADJUSTMENT.value)
        self.assertEqual(last_change["payload"]["layer"], "consequences")

    def test_add_convict(self):
        """Test adding a new belief and consolidation."""
        convict = {"belief": "Rust is faster", "confidence": 0.95}
        self.mission.add_convict(convict)

        self.assertEqual(len(self.mission.adaptive_beliefs), 1)
        self.assertEqual(self.mission.adaptive_beliefs[0]["belief"], "Rust is faster")

        # Check history for create
        last_change = self.mission.history[-1]
        self.assertEqual(last_change["type"], MissionChangeType.NEW_CONVICT.value)
        self.assertEqual(last_change["payload"]["action"], "create")

        # Update existing
        convict_update = {"belief": "Rust is faster", "confidence": 0.99}
        self.mission.add_convict(convict_update)

        self.assertEqual(len(self.mission.adaptive_beliefs), 1)
        self.assertEqual(self.mission.adaptive_beliefs[0]["confidence"], 0.99)

        # Check history for update
        last_change = self.mission.history[-1]
        self.assertEqual(last_change["payload"]["action"], "update")

    def test_get_summary(self):
        """Test summary generation."""
        summary = self.mission.get_summary()
        self.assertIn("core_principles_count", summary)
        self.assertIn("adaptive_beliefs_count", summary)
        self.assertIn("total_changes", summary)
        self.assertIn("core_principles", summary) # Check for list presence

if __name__ == '__main__':
    unittest.main()
