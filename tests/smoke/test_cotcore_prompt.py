import queue
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from llm import llm_module


class DummyAdapter:
    def __init__(self):
        self.calls = []

    def process(self, question: str, prompt: str) -> str:
        self.calls.append((question, prompt))
        return f"wrapped::{prompt}"


class TestCOTCorePrompt(unittest.TestCase):
    def test_compose_prompt_without_cotcore(self):
        model = llm_module.LanguageModel(queue.Queue(), queue.Queue(), use_cotcore=False)
        prompt = model._compose_prompt("hello")

        self.assertIsNone(model.cot_adapter)
        self.assertIn("hello", prompt)

    def test_compose_prompt_with_cotcore(self):
        base_model = llm_module.LanguageModel(queue.Queue(), queue.Queue(), use_cotcore=False)
        base_prompt = base_model._compose_prompt("hello")

        with patch.object(llm_module, "COTAdapter", DummyAdapter):
            model = llm_module.LanguageModel(queue.Queue(), queue.Queue(), use_cotcore=True)
            prompt = model._compose_prompt("hello")

        self.assertEqual(prompt, f"wrapped::{base_prompt}")
        self.assertEqual(model.cot_adapter.calls[0][0], "hello")


if __name__ == "__main__":
    unittest.main()
