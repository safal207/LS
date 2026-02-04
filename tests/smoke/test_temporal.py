import time
import unittest

from llm.temporal import TemporalContext


class TestTemporalContext(unittest.TestCase):
    def test_transitions_and_age(self):
        ctx = TemporalContext()
        self.assertEqual(ctx.state, "idle")
        start = ctx.last_transition
        ctx.transition("thinking")
        self.assertEqual(ctx.state, "thinking")
        self.assertGreaterEqual(ctx.last_transition, start)
        self.assertGreaterEqual(ctx.age(), 0.0)


if __name__ == "__main__":
    unittest.main()
