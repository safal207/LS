import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from modes.mode_a import FastMode, ModeAResponse


class TestModeAHeuristics(unittest.TestCase):
    def setUp(self):
        self.mode_a = FastMode()

    def test_temporal_time(self):
        response = self.mode_a.process("time")
        self.assertEqual(response.source, "temporal_lookup")
        self.assertRegex(response.result, r"\d{2}:\d{2}")

    def test_temporal_date(self):
        response = self.mode_a.process("date")
        self.assertEqual(response.source, "temporal_lookup")
        self.assertRegex(response.result, r"\d{4}-\d{2}-\d{2}")

    def test_temporal_day(self):
        response = self.mode_a.process("day")
        self.assertEqual(response.source, "temporal_lookup")
        self.assertIn(response.result, [
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday"
        ])

    def test_math_addition(self):
        response = self.mode_a.process("2+2")
        self.assertEqual(response.source, "math")
        self.assertEqual(response.result, "4")

    def test_math_subtraction(self):
        response = self.mode_a.process("10-3")
        self.assertEqual(response.source, "math")
        self.assertEqual(response.result, "7")

    def test_math_multiplication(self):
        response = self.mode_a.process("4*5")
        self.assertEqual(response.source, "math")
        self.assertEqual(response.result, "20")

    def test_math_division(self):
        response = self.mode_a.process("20/4")
        self.assertEqual(response.source, "math")
        self.assertEqual(response.result, "5.0")

    def test_math_multiple_ops(self):
        response = self.mode_a.process("2+3*4")
        self.assertEqual(response.source, "math")
        self.assertEqual(response.result, "20")

    def test_math_too_many_ops_rejected(self):
        response = self.mode_a.process("1+2+3+4+5")
        self.assertEqual(response.source, "echo")

    def test_string_len(self):
        response = self.mode_a.process("len hello")
        self.assertEqual(response.source, "string_command")
        self.assertEqual(response.result, "5")

    def test_string_rev(self):
        response = self.mode_a.process("rev hello")
        self.assertEqual(response.source, "string_command")
        self.assertEqual(response.result, "olleh")

    def test_string_trim(self):
        response = self.mode_a.process("trim   hello   ")
        self.assertEqual(response.source, "string_command")
        self.assertEqual(response.result, "hello")

    def test_string_upper(self):
        response = self.mode_a.process("upper hello")
        self.assertEqual(response.source, "string_command")
        self.assertEqual(response.result, "HELLO")

    def test_string_lower(self):
        response = self.mode_a.process("lower HELLO")
        self.assertEqual(response.source, "string_command")
        self.assertEqual(response.result, "hello")

    def test_string_words(self):
        response = self.mode_a.process("words hello world foo")
        self.assertEqual(response.source, "string_command")
        self.assertEqual(response.result, "3")

    def test_nlu_greeting_hi(self):
        response = self.mode_a.process("hi")
        self.assertEqual(response.source, "mini_nlu")
        self.assertIn("Hello", response.result)

    def test_nlu_thanks(self):
        response = self.mode_a.process("thanks")
        self.assertEqual(response.source, "mini_nlu")
        self.assertIn("welcome", response.result.lower())

    def test_echo_fallback(self):
        response = self.mode_a.process("random text")
        self.assertEqual(response.source, "echo")
        self.assertEqual(response.result, "random text")

    def test_cache_hit(self):
        response1 = self.mode_a.process("time")
        self.assertFalse(response1.cache_hit)
        response2 = self.mode_a.process("time")
        self.assertTrue(response2.cache_hit)
        self.assertEqual(response2.source, "cache")

    def test_cache_case_insensitive(self):
        response1 = self.mode_a.process("time")
        response2 = self.mode_a.process("TIME")
        self.assertTrue(response2.cache_hit)
        self.assertEqual(response1.result, response2.result)

    def test_cache_lru_eviction(self):
        small = FastMode(cache_size=2)
        small.process("len test1")
        small.process("len test2")
        small.process("len test3")
        self.assertEqual(len(small.cache), 2)
        self.assertNotIn("len test1", small.cache)

    def test_cache_clear(self):
        self.mode_a.process("time")
        self.assertGreater(len(self.mode_a.cache), 0)
        self.mode_a.clear_cache()
        self.assertEqual(len(self.mode_a.cache), 0)

    def test_load_aware_disables_heavy_ops(self):
        response_normal = self.mode_a.process("rev hello", system_load=0.2)
        self.assertEqual(response_normal.source, "string_command")
        response_heavy = self.mode_a.process("rev hello", system_load=0.9)
        self.assertEqual(response_heavy.result, "Not available (system under load)")

    def test_load_aware_keeps_light_ops(self):
        response = self.mode_a.process("upper hello", system_load=0.9)
        self.assertEqual(response.source, "string_command")
        self.assertEqual(response.result, "HELLO")

    def test_response_includes_metadata(self):
        response = self.mode_a.process("time", system_load=0.5)
        self.assertIsInstance(response, ModeAResponse)
        self.assertIsNotNone(response.result)
        self.assertIsNotNone(response.source)
        self.assertGreaterEqual(response.execution_time_ms, 0)
        self.assertIsInstance(response.cache_hit, bool)
        self.assertEqual(response.load_factor, 0.5)

    def test_response_to_dict(self):
        response = self.mode_a.process("time")
        response_dict = response.to_dict()
        self.assertIsInstance(response_dict, dict)
        self.assertIn("result", response_dict)
        self.assertIn("source", response_dict)
        self.assertIn("execution_time_ms", response_dict)

    def test_determinism_same_input_same_output(self):
        responses = [self.mode_a.process("len hello") for _ in range(5)]
        results = [r.result for r in responses]
        self.assertTrue(all(r == results[0] for r in results))


class TestModeAPerformance(unittest.TestCase):
    def setUp(self):
        self.mode_a = FastMode()

    def test_cache_hit_is_fast(self):
        self.mode_a.process("time")
        response = self.mode_a.process("time")
        self.assertTrue(response.cache_hit)
        self.assertLess(response.execution_time_ms, 10)


if __name__ == "__main__":
    unittest.main()
