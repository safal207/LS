import queue
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from llm.errors import LLMEmptyResponseError
from llm.llm_module import LanguageModel


class TestLLMErrors(unittest.TestCase):
    def test_timeout_trips_breaker(self):
        lm = LanguageModel(queue.Queue(), queue.Queue(), use_breaker=True)
        lm.qwen_handler.generate_response = MagicMock(side_effect=TimeoutError("timeout"))

        self.assertIsNotNone(lm.breaker)
        result = lm.generate_response_local("hi")
        self.assertIsNone(result)
        self.assertEqual(lm.breaker._failure_count, 1)

    def test_empty_response_does_not_trip_or_reset_breaker(self):
        lm = LanguageModel(queue.Queue(), queue.Queue(), use_breaker=True)

        lm.qwen_handler.generate_response = MagicMock(side_effect=RuntimeError("fail"))
        self.assertIsNone(lm.generate_response_local("hi"))
        self.assertEqual(lm.breaker._failure_count, 1)

        lm.qwen_handler.generate_response = MagicMock(side_effect=LLMEmptyResponseError())
        self.assertIsNone(lm.generate_response_local("hi"))
        self.assertEqual(lm.breaker._failure_count, 1)

    def test_invalid_format_trips_breaker(self):
        lm = LanguageModel(queue.Queue(), queue.Queue(), use_breaker=True)
        lm.qwen_handler.generate_response = MagicMock(return_value={"not": "a string"})

        self.assertIsNone(lm.generate_response_local("hi"))
        self.assertEqual(lm.breaker._failure_count, 1)


if __name__ == "__main__":
    unittest.main()
