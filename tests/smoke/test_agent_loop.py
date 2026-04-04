import queue
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from agent.loop import AgentLoop


class DummyLLM:
    def generate_response(self, question: str):
        return "ok"

    def format_response(self, response: str) -> str:
        return response


class TestAgentLoop(unittest.TestCase):
    def test_handle_input_sets_idle(self):
        output_queue = queue.Queue()
        loop = AgentLoop(output_queue=output_queue, llm=DummyLLM())

        loop.handle_input("hi")

        payload = output_queue.get_nowait()
        self.assertIn("response", payload)
        self.assertIn("mode_explanation", payload)
        self.assertIsNotNone(loop.temporal)
        self.assertEqual(loop.temporal.state, "idle")

    def test_subconscious_pass_creates_latest_insight(self):
        loop = AgentLoop(output_queue=queue.Queue(), llm=DummyLLM())
        loop.memory["history"] = [
            {"role": "user", "content": "how does this work"},
            {"role": "assistant", "content": "answer"},
            {"role": "user", "content": "why does it fail on edge cases"},
            {"role": "assistant", "content": "answer"},
        ]

        loop._run_subconscious_pass()

        latest = loop.memory.get("subconscious_latest")
        self.assertIsInstance(latest, dict)
        self.assertIn("suggested_mode", latest)
        self.assertIn("route", latest)

    def test_subconscious_feeds_temporal_graph(self):
        """Subconscious pass should create a TemporalNode in the temporal graph."""
        loop = AgentLoop(output_queue=queue.Queue(), llm=DummyLLM())
        loop.memory["history"] = [
            {"role": "user", "content": "why does this happen"},
            {"role": "assistant", "content": "answer"},
            {"role": "user", "content": "how can I explain this to someone else"},
            {"role": "assistant", "content": "answer"},
        ]

        loop._run_subconscious_pass()

        # TemporalGraph should have a node for the detected mode
        latest = loop.memory.get("subconscious_latest", {})
        mode = latest.get("suggested_mode")
        self.assertIsNotNone(mode)
        node_id = f"subconscious:{mode}"
        self.assertIn(node_id, loop.temporal.nodes)
        node = loop.temporal.nodes[node_id]
        self.assertGreater(node.resonance, 0.0)

    def test_subconscious_resonance_accumulates(self):
        """Repeated subconscious passes on same mode should strengthen the TemporalNode."""
        loop = AgentLoop(output_queue=queue.Queue(), llm=DummyLLM())
        deliberative_history = [
            {"role": "user", "content": "why does this algorithm fail on large inputs"},
            {"role": "assistant", "content": "answer"},
            {"role": "user", "content": "can you explain the reason in more depth"},
            {"role": "assistant", "content": "answer"},
        ]
        loop.memory["history"] = deliberative_history

        loop._run_subconscious_pass()
        first_resonance = loop.temporal.nodes.get("subconscious:deliberative")
        self.assertIsNotNone(first_resonance)
        r1 = first_resonance.resonance

        loop._run_subconscious_pass()
        r2 = loop.temporal.nodes["subconscious:deliberative"].resonance

        self.assertGreater(r2, r1, "Resonance should increase on repeated detection")

    def test_positive_feedback_strengthens_temporal_node(self):
        """Positive user signal boosts resonance of the last active mode node."""
        loop = AgentLoop(output_queue=queue.Queue(), llm=DummyLLM())

        from hexagon_core.temporal_graph import TemporalNode
        loop.temporal.nodes["subconscious:deliberative"] = TemporalNode(
            id="subconscious:deliberative", resonance=0.75, harmony_bonus=0.1
        )
        loop.memory["subconscious_latest"] = {
            "suggested_mode": "deliberative",
            "hypothesis": "test",
            "confidence": 0.78,
        }

        loop._apply_quality_feedback("positive", "да, точно")

        node = loop.temporal.nodes["subconscious:deliberative"]
        self.assertGreater(node.resonance, 0.75)
        self.assertEqual(loop.memory["feedback_log"][-1]["signal"], "positive")

    def test_negative_feedback_weakens_temporal_node(self):
        """Negative user signal reduces resonance of the last active mode node."""
        loop = AgentLoop(output_queue=queue.Queue(), llm=DummyLLM())

        from hexagon_core.temporal_graph import TemporalNode
        loop.temporal.nodes["subconscious:reactive"] = TemporalNode(
            id="subconscious:reactive", resonance=0.80, harmony_bonus=0.1
        )
        loop.memory["subconscious_latest"] = {
            "suggested_mode": "reactive",
            "hypothesis": "test",
            "confidence": 0.66,
        }

        loop._apply_quality_feedback("negative", "нет, не то")

        node = loop.temporal.nodes["subconscious:reactive"]
        self.assertLess(node.resonance, 0.80)

    def test_feedback_creates_node_if_missing(self):
        """Positive feedback creates a TemporalNode if it doesn't exist yet."""
        loop = AgentLoop(output_queue=queue.Queue(), llm=DummyLLM())
        loop.memory["subconscious_latest"] = {
            "suggested_mode": "creative",
            "hypothesis": "test",
            "confidence": 0.76,
        }

        loop._apply_quality_feedback("positive", "отлично")

        self.assertIn("subconscious:creative", loop.temporal.nodes)

    def test_ingest_reflection_creates_lesson_node(self):
        """ingest_reflection() should create a lesson: TemporalNode with correct resonance."""
        from hexagon_core.temporal_graph import TemporalGraph

        tg = TemporalGraph()
        node = tg.ingest_reflection("Goal moved closer: completion 0.40 -> 0.70.", progress=0.5)

        self.assertTrue(node.id.startswith("lesson:"))
        # resonance = 0.5 + 0.5 * 0.45 = 0.725 base, may be slightly higher after align_to_axis
        self.assertGreaterEqual(node.resonance, 0.72)
        self.assertLessEqual(node.resonance, 1.0)
        self.assertEqual(node.harmony_bonus, 0.35)
        self.assertIn(node.id, tg.nodes)

    def test_ingest_reflection_negative_progress_lowers_resonance(self):
        """Negative progress should produce resonance < 0.5."""
        from hexagon_core.temporal_graph import TemporalGraph

        tg = TemporalGraph()
        node = tg.ingest_reflection("Goal moved farther: completion 0.70 -> 0.40.", progress=-0.5)

        self.assertLess(node.resonance, 0.5)

    def test_ingest_reflection_repeated_strengthens_node(self):
        """Ingesting the same reflection twice should strengthen (not duplicate) the node."""
        from hexagon_core.temporal_graph import TemporalGraph

        tg = TemporalGraph()
        n1 = tg.ingest_reflection("lesson repeated test", progress=0.3)
        r1 = n1.resonance
        n2 = tg.ingest_reflection("lesson repeated test", progress=0.6)

        self.assertEqual(n1.id, n2.id)  # same node, not duplicated
        self.assertGreaterEqual(n2.resonance, r1)

    def test_lesson_node_can_become_axis(self):
        """A high-resonance lesson node should win the meritocratic axis."""
        from hexagon_core.temporal_graph import TemporalGraph, TemporalNode

        tg = TemporalGraph()
        # Competing subconscious node
        tg.nodes["subconscious:reactive"] = TemporalNode(
            id="subconscious:reactive", resonance=0.70, harmony_bonus=0.1
        )
        # Strong lesson from reflection
        lesson = tg.ingest_reflection("deliberative approach worked well here", progress=0.9)

        axis = tg.get_meritocratic_axis()
        self.assertTrue(axis.id.startswith("lesson:"))

    def test_velocity_calculated_on_resonance_update(self):
        """update_resonance() should set non-zero velocity after a change."""
        from hexagon_core.temporal_graph import TemporalNode
        import time

        node = TemporalNode(id="test:node", resonance=0.50, harmony_bonus=0.1)
        time.sleep(0.05)  # ensure delta_t > 0
        node.update_resonance(0.80)

        # velocity should be positive (resonance went up)
        self.assertGreater(node.velocity, 0.0)
        self.assertAlmostEqual(node.resonance, 0.80, places=5)

    def test_velocity_leaders_returns_fastest_growing(self):
        """velocity_leaders() returns nodes sorted by velocity descending."""
        from hexagon_core.temporal_graph import TemporalGraph, TemporalNode
        import time

        tg = TemporalGraph()
        slow = TemporalNode(id="slow", resonance=0.5, harmony_bonus=0.0)
        fast = TemporalNode(id="fast", resonance=0.5, harmony_bonus=0.0)
        time.sleep(0.05)
        slow.update_resonance(0.55)   # small delta
        fast.update_resonance(0.90)   # large delta
        tg.nodes["slow"] = slow
        tg.nodes["fast"] = fast

        leaders = tg.velocity_leaders(n=2)
        self.assertEqual(leaders[0][0], "fast")
        self.assertGreater(leaders[0][1], leaders[1][1])

    def test_fast_growing_node_wins_axis_over_stale_high_resonance(self):
        """A fast-growing node should beat a stale high-resonance node on axis."""
        from hexagon_core.temporal_graph import TemporalGraph, TemporalNode
        import time

        tg = TemporalGraph()
        # Stale high-resonance node — hasn't changed recently, velocity ≈ 0
        stale = TemporalNode(id="subconscious:reactive", resonance=0.88, harmony_bonus=0.1)
        tg.nodes["subconscious:reactive"] = stale

        # Fast-growing node — just got strong positive feedback
        rising = TemporalNode(id="subconscious:deliberative", resonance=0.70, harmony_bonus=0.1)
        time.sleep(0.05)
        rising.update_resonance(0.70 + 0.18 + 0.18)   # two rapid positive feedbacks
        tg.nodes["subconscious:deliberative"] = rising

        axis = tg.get_meritocratic_axis()
        # The rising node should win because its velocity_score pushes it ahead
        self.assertEqual(axis.id, "subconscious:deliberative")

    def test_temporal_axis_drives_explanation_hint(self):
        """When TemporalGraph axis is a high-resonance subconscious node, explanation includes it."""
        loop = AgentLoop(output_queue=queue.Queue(), llm=DummyLLM())

        # Manually inject a high-resonance temporal node
        from hexagon_core.temporal_graph import TemporalNode
        loop.temporal.nodes["subconscious:deliberative"] = TemporalNode(
            id="subconscious:deliberative", resonance=0.92, harmony_bonus=0.2
        )

        explanation = loop._explain_mode_for_item("why?", {})
        self.assertIn("deliberative", explanation)
        self.assertIn("резонанс", explanation)


if __name__ == "__main__":
    unittest.main()
