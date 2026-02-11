import unittest
import sys
from pathlib import Path

# Ensure python/ directory is in sys.path
sys.path.append(str(Path(__file__).parent.parent))

from modules.hexagon_core.capu_v3 import CaPUv3

class TestCaPUv3(unittest.TestCase):
    def setUp(self):
        self.capu = CaPUv3()
        # Mocking data loading
        self.capu.facts = {"test_fact": "This is a fact."}
        self.capu.logic = [{"keywords": ["logic"], "decision": "Use Logic", "reason": "It works"}]
        self.capu._loaded = True

    def test_store_intent_with_alignment(self):
        """Test that storing intent calculates mission alignment."""
        self.capu.store_intent("Refactor code", "context")
        self.assertIsNotNone(self.capu._intent)
        self.assertIn("alignment", self.capu._intent)
        self.assertEqual(self.capu._intent["alignment"]["recommendation"], "proceed")

    def test_cold_storage_archiving(self):
        """Test that old data moves to cold storage."""
        self.capu.archive_threshold = 2

        self.capu.store_procedure("Task 1", ["Step 1"])
        self.capu.store_procedure("Task 2", ["Step 2"])
        self.capu.store_procedure("Task 3", ["Step 3"]) # Should trigger archive of Task 1

        self.assertEqual(len(self.capu._procedures), 2)
        self.assertEqual(self.capu._procedures[0]["task"], "Task 2")
        self.assertEqual(len(self.capu.cold_storage), 1)
        self.assertEqual(self.capu.cold_storage[0]["data"]["task"], "Task 1")

    def test_layer_prioritization_rendering(self):
        """Test that prompt sections are ordered by weight."""
        # Set weights: Consequences (0.9) > Predictions (0.1)
        self.capu.mission.weights["consequences"] = 0.9
        self.capu.mission.weights["predictions"] = 0.1

        self.capu.store_prediction("Pred", "Result", 0.5)
        self.capu.store_consequence("If", "Then", "High")

        ctx = self.capu.build_cognitive_context("query")
        prompt = self.capu.render_cognitive_prompt("query", ctx)

        # Verify Consequences appear before Predictions in FUTURE section
        future_idx = prompt.find("### FUTURE PROJECTIONS ###")
        cons_idx = prompt.find("⚠️ CONSEQUENCE ANALYSIS:", future_idx)
        pred_idx = prompt.find("🔮 PREDICTIONS:", future_idx)

        self.assertNotEqual(future_idx, -1)
        self.assertNotEqual(cons_idx, -1)
        self.assertNotEqual(pred_idx, -1)
        self.assertLess(cons_idx, pred_idx)

    def test_render_full_prompt_elements(self):
        """Test that Mission, CTE, and Convicts appear."""
        self.capu.store_intent("Test", "ctx")
        self.capu.commit_transition("Decision A")
        self.capu.register_outcome("Outcome B") # Forms convict

        ctx = self.capu.build_cognitive_context("query")
        prompt = self.capu.render_cognitive_prompt("query", ctx)

        self.assertIn("Mission alignment", prompt)
        self.assertIn("📜 MISSION:", prompt)
        self.assertIn("🔒 ACTIVE CHOICE", prompt)
        self.assertIn("💡 LAST OUTCOME", prompt)
        self.assertIn("### CONVICTS (FORMED BELIEFS) ###", prompt)

if __name__ == '__main__':
    unittest.main()
