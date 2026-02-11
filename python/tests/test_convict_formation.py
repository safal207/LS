import unittest
import sys
import time
from pathlib import Path
from datetime import timedelta

# Ensure python/ directory is in sys.path
sys.path.append(str(Path(__file__).parent.parent))

from modules.hexagon_core.capu_v3 import CaPUv3

class TestConvictFormation(unittest.TestCase):
    def setUp(self):
        self.capu = CaPUv3()
        # Reduce cooldown for testing
        self.capu.lifecycle.tracker.cooldown = timedelta(milliseconds=1)

    def test_form_convict_from_outcome(self):
        """Test forming a convict from a registered outcome via CaPU."""
        self.capu.commit_transition("Learn Python")
        res = self.capu.register_outcome("Python is versatile", outcome_type="insight")

        self.assertEqual(res["status"], "success")
        self.assertIn("convict_id", res)

        # Verify it's in the system
        convicts = self.capu.lifecycle.get_active_beliefs()
        self.assertEqual(len(convicts), 1)
        self.assertEqual(convicts[0].belief, "Python is versatile")

    def test_validate_strengthens_convict(self):
        """Test that validation increases confidence."""
        self.capu.commit_transition("A")
        self.capu.register_outcome("Sky is blue")

        c = self.capu.lifecycle.get_active_beliefs()[0]
        initial_conf = c.confidence

        # Ensure time passes for cooldown (we set it to 1ms)
        time.sleep(0.01)

        # Validate via duplicate outcome
        self.capu.commit_transition("A again")
        self.capu.register_outcome("Sky is blue")

        c_updated = self.capu.lifecycle.get_active_beliefs()[0]
        self.assertGreater(c_updated.confidence, initial_conf)

if __name__ == '__main__':
    unittest.main()
