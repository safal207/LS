import queue
import threading
import time
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


class TestTemporalFlow(unittest.TestCase):
    def test_temporal_returns_idle(self):
        input_queue = queue.Queue()
        output_queue = queue.Queue()
        lm = LanguageModel(input_queue, output_queue, use_cotcore=False)
        self.assertIsNotNone(lm.temporal)
        lm.test_ollama_connection = MagicMock(return_value=True)
        lm.qwen_handler.generate_response = MagicMock(return_value="ok")

        thread = threading.Thread(target=lm.run, daemon=True)
        thread.start()

        input_queue.put({
            "type": "question",
            "text": "hi",
            "timestamp": time.time(),
        })

        output_queue.get(timeout=5)
        lm.stop()
        thread.join(timeout=5)

        self.assertEqual(lm.temporal.state, "idle")


if __name__ == "__main__":
    unittest.main()
