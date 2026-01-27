import unittest
import sys
from pathlib import Path

# Ensure python/ directory is in sys.path
sys.path.append(str(Path(__file__).parent.parent))

from modules.hexagon_core.cte import CognitiveTimelineEngine

class TestConvictFormation(unittest.TestCase):
    def setUp(self):
        self.cte = CognitiveTimelineEngine()

    def test_form_convict_from_outcome(self):
        """Test forming a convict from a registered outcome."""
        self.cte.commit_transition("Learn Python")
        res = self.cte.register_outcome("Python is versatile", outcome_type="insight")

        self.assertEqual(res["status"], "success")
        self.assertIsNotNone(res["convict"])
        self.assertEqual(res["convict"]["belief"], "Python is versatile")

        # Verify it's in the system
        convicts = self.cte.get_convicts()
        self.assertEqual(len(convicts), 1)
        self.assertEqual(convicts[0]["belief"], "Python is versatile")

    def test_validate_strengthens_convict(self):
        """Test that validation increases confidence."""
        self.cte.commit_transition("A")
        self.cte.register_outcome("Sky is blue")

        c_initial = self.cte.get_convicts()[0]
        initial_conf = c_initial["confidence"]
        initial_strength = c_initial["strength"]

        # Validate via duplicate outcome (simulated) or direct access
        # Since register_outcome calls form_convict which calls validate if exists...
        self.cte.commit_transition("A again")
        self.cte.register_outcome("Sky is blue")

        c_updated = self.cte.get_convicts()[0]
        self.assertGreater(c_updated["confidence"], initial_conf)
        self.assertGreater(c_updated["strength"], initial_strength)

    def test_get_convicts_filtering(self):
        """Test filtering by confidence."""
        # Manually inject convicts
        from modules.hexagon_core.cte import Convict
        self.cte._convicts["weak"] = Convict("weak", {}, 0.4, "test", 1, 0, 0)
        self.cte._convicts["strong"] = Convict("strong", {}, 0.9, "test", 1, 0, 0)

        results = self.cte.get_convicts(min_confidence=0.7)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["belief"], "strong")

if __name__ == '__main__':
    unittest.main()
