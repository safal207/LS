import unittest
import sys
from pathlib import Path

# Ensure python/ directory is in sys.path
sys.path.append(str(Path(__file__).parent.parent))

from modules.hexagon_core.cte import CognitiveTimelineEngine

class TestOscillationControl(unittest.TestCase):
    def setUp(self):
        self.cte = CognitiveTimelineEngine()
        self.cte.oscillation_threshold = 3 # Threshold = 3, so 2 ABAB checks.

    def test_refinement_is_allowed(self):
        """Test that refinement is NOT treated as oscillation."""
        # A
        self.cte.commit_transition("Deploy to production")
        self.cte.active_anchor_id = None # Simulate resolution

        # A' (Refinement)
        res = self.cte.commit_transition("Deploy to production server 1")
        self.assertEqual(res["status"], "created")

        # Check oscillation manually
        osc = self.cte.check_oscillation("Deploy to production server 1")
        self.assertFalse(osc["is_oscillating"])

    def test_oscillation_detection_and_locking(self):
        """Test detection of ABAB pattern and eventual locking."""
        # We need to simulate a sequence of committed transitions (A, B, A, B...)
        # Note: check_oscillation looks at HISTORY of ANCHORS + current proposal.

        # 1. A
        self.cte.commit_transition("Option A")
        self.cte.active_anchor_id = None # Resolve

        # 2. B
        self.cte.commit_transition("Option B")
        self.cte.active_anchor_id = None

        # 3. A (1st oscillation cycle A->B->A) - Should be ALLOWED but detected?
        # check_oscillation for A:
        # History: A, B. New: A. Sequence: A, B, A.
        # AB count: 1 (B->A). Wait, logic is ABAB (count 2).
        # So A->B->A is count 1? A(-3), B(-2), A(-1). Pair (B, A) at -2,-1. Previous (A, B) at -3,-2? No.
        # Logic looks for PAIRS (A, B).
        # A, B, A. Last pair is (B, A). Previous pair? None.
        # So this should be allowed.
        res = self.cte.commit_transition("Option A")
        self.assertEqual(res["status"], "created")
        self.cte.active_anchor_id = None

        # 4. B (2nd oscillation cycle A->B->A->B) - This makes AB count 2?
        # History: A, B, A. New: B. Sequence: A, B, A, B.
        # Last pair (A, B). Previous pair (B, A)? No, we check for SAME pair (A, B).
        # Pairs: (A, B) at end. Preceded by (A, B) at start.
        # Yes! Count = 2.
        # Threshold is 3. So severity = 2/3 = 0.66. Recommendation = reject.
        res = self.cte.commit_transition("Option B")
        self.assertEqual(res["status"], "rejected_oscillation")
        self.assertEqual(res["oscillation"]["recommendation"], "reject")

        # 5. Lock scenario
        # Force commit B to simulate persistence (or reduce threshold for test)
        # Let's set threshold to 2 to trigger lock now.
        self.cte.oscillation_threshold = 2
        res = self.cte.commit_transition("Option B")
        self.assertEqual(res["status"], "rejected_oscillation")
        self.assertEqual(res["oscillation"]["recommendation"], "lock")
        self.assertTrue(self.cte.locked_due_to_oscillation)

    def test_reset_lock(self):
        self.cte.locked_due_to_oscillation = True
        self.cte.reset_oscillation_lock()
        self.assertFalse(self.cte.locked_due_to_oscillation)

if __name__ == '__main__':
    unittest.main()
