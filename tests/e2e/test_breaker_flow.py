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

for name in ["requests"]:
    sys.modules.setdefault(name, MagicMock())

from llm.llm_module import LanguageModel


class TestBreakerFlow(unittest.TestCase):
    def test_breaker_fallback(self):
        lm = LanguageModel(queue.Queue(), queue.Queue(), use_breaker=True)
        lm.qwen_handler.generate_response = MagicMock(side_effect=RuntimeError("fail"))

        # First three calls fail
        for _ in range(3):
            result = lm.generate_response_local("Hello")
            self.assertIsNone(result)

        # Breaker now open; should return fallback
        result = lm.generate_response_local("Hello")
        self.assertEqual(result, "LLM temporarily unavailable. Please try again later.")


if __name__ == "__main__":
    unittest.main()
