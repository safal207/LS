import unittest
from unittest.mock import MagicMock, patch
import sys
import os
from pathlib import Path

# Ensure python/ directory is in sys.path
sys.path.append(str(Path(__file__).parent.parent))

from modules.hexagon_core.capu_v3 import CaPUv3, CognitiveContext

class TestCaPUv3(unittest.TestCase):
    def setUp(self):
        self.capu = CaPUv3()
        # Mocking data loading to avoid filesystem dependency during tests
        self.capu.facts = {"test_fact": "This is a fact."}
        self.capu.logic = [{"keywords": ["logic"], "decision": "Use Logic", "reason": "It works"}]
        self.capu._loaded = True

    def test_store_layers(self):
        """Test storing data in all new cognitive layers."""
        self.capu.store_intent("Fix bugs", "Testing context")
        self.capu.store_target("Developer", "Code review")
        self.capu.store_procedure("Run tests", ["Step 1", "Step 2"])
        self.capu.store_duration("Coding", 120.5)
        self.capu.store_prediction("Tests pass", "Merge", 0.95)
        self.capu.store_consequence("Bug found", "Fix it", "High")

        self.assertIsNotNone(self.capu._intent)
        self.assertEqual(self.capu._intent["intent"], "Fix bugs")
        self.assertEqual(self.capu._target["for_whom"], "Developer")
        self.assertEqual(len(self.capu._procedures), 1)
        self.assertEqual(self.capu._procedures[0]["task"], "Run tests")
        self.assertEqual(len(self.capu._durations), 1)
        self.assertEqual(self.capu._durations[0]["event"], "Coding")
        self.assertEqual(len(self.capu._predictions), 1)
        self.assertEqual(self.capu._predictions[0]["confidence"], 0.95)
        self.assertEqual(len(self.capu._consequences), 1)
        self.assertEqual(self.capu._consequences[0]["severity"], "High")

    def test_build_cognitive_context(self):
        """Test aggregation of data into CognitiveContext."""
        # Setup data
        self.capu.store_intent("Test Intent", "Context")
        self.capu.update_history("user", "Hello")

        # Query that matches fact and logic
        ctx = self.capu.build_cognitive_context("test_fact logic")

        self.assertIsInstance(ctx, CognitiveContext)
        # Check v2 layers
        self.assertTrue(any("test_fact" in f for f in ctx.facts))
        # Logic matches "logic" keyword which is in "keywords": ["logic"]?
        # Wait, my mock logic has keyword "logic". The query has "logic".
        # Let's verify _matches_query logic.
        # It uses strict word boundaries. "logic" matches "logic".
        # But wait, logic trigger words are needed: ["why", "reason", ...]
        # My query "test_fact logic" does not contain a trigger word.
        # So logic might be empty.

        # Let's add a trigger word to query
        ctx = self.capu.build_cognitive_context("why use logic test_fact")
        self.assertTrue(len(ctx.logic) > 0)

        # Check v3 layers
        self.assertIsNotNone(ctx.intent)
        self.assertEqual(ctx.intent["intent"], "Test Intent")
        self.assertEqual(len(ctx.history), 1)

    def test_render_cognitive_prompt(self):
        """Test the Cognitive Timeline Engine output."""
        self.capu.store_intent("Solve world hunger", "Global context")
        self.capu.store_prediction("Plan works", "Peace", 1.0)
        self.capu.update_history("user", "How do I do it?")

        ctx = self.capu.build_cognitive_context("How do I do it?")
        prompt = self.capu.render_cognitive_prompt("How do I do it?", ctx)

        # Check for headers
        self.assertIn("### META-COGNITION ###", prompt)
        self.assertIn("🧠 INTENT: Solve world hunger", prompt)
        self.assertIn("### PAST TIMELINE ###", prompt)
        self.assertIn("💬 RECENT HISTORY:", prompt)
        self.assertIn("### FUTURE PROJECTIONS ###", prompt)
        self.assertIn("🔮 Plan works -> Peace", prompt)
        self.assertIn("🚀 INSTRUCTION: You are CaPU v3", prompt)

    def test_compatibility(self):
        """Test construct_prompt wrapper."""
        prompt = self.capu.construct_prompt("Simple query")
        self.assertIsInstance(prompt, str)
        self.assertIn("❓ CURRENT QUERY: Simple query", prompt)

    def test_cte_liminal_and_insight(self):
        """CTE: liminal anchor + insight appear in META-COGNITION."""
        self.capu.store_intent("Refactor core", "Architecture evolution")
        self.capu.commit_transition("Switch to Rust Core", ["Stay on Python"])
        self.capu.register_outcome("Rust improved latency 100x", "insight")

        ctx = self.capu.build_cognitive_context("Why Rust?")
        prompt = self.capu.render_cognitive_prompt("Why Rust?", ctx)

        self.assertIn("🔒 ACTIVE CHOICE", prompt)
        self.assertIn("Switch to Rust Core", prompt)
        self.assertIn("💡 LAST OUTCOME", prompt)
        self.assertIn("Rust improved latency 100x", prompt)

if __name__ == '__main__':
    unittest.main()
