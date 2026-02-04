import queue
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

for name in ["pyaudio", "numpy", "soundfile", "faster_whisper", "requests", "psutil"]:
    sys.modules.setdefault(name, MagicMock())

import importlib
console_main = importlib.import_module("apps.console.main")


class FakeAudio:
    def __init__(self, output_queue: queue.Queue):
        self.output_queue = output_queue
        self.running = False

    def run(self):
        self.running = True
        try:
            self.output_queue.put_nowait("dummy.wav")
        except Exception:
            pass

    def stop(self):
        self.running = False


class FakeSTT:
    def __init__(self, input_queue: queue.Queue, output_queue: queue.Queue):
        self.input_queue = input_queue
        self.output_queue = output_queue

    def run(self):
        try:
            self.input_queue.get(timeout=0.1)
        except Exception:
            return
        self.output_queue.put({
            "type": "question",
            "text": "What is Python?",
            "timestamp": time.time(),
        })

    def stop(self):
        return None


class FakeLLM:
    def __init__(self, input_queue: queue.Queue, output_queue: queue.Queue):
        self.input_queue = input_queue
        self.output_queue = output_queue

    def run(self):
        try:
            item = self.input_queue.get(timeout=0.1)
        except Exception:
            return
        self.output_queue.put({
            "question": item.get("text"),
            "response": "Answer",
            "generation_time": 0.01,
            "timestamp": time.time(),
        })

    def stop(self):
        return None


class TestConsoleFlow(unittest.TestCase):
    def test_flow_starts_and_stops(self):
        console_main.AudioIngestion = FakeAudio
        console_main.SpeechToText = FakeSTT
        console_main.LanguageModel = FakeLLM
        console_main.check_system_resources = lambda: True
        console_main.InterviewCopilot._ui_display_loop = lambda self: None

        orig_sleep = console_main.time.sleep
        console_main.time.sleep = lambda _: orig_sleep(0.01)

        try:
            copilot = console_main.InterviewCopilot()
            worker = threading.Thread(target=copilot.start)
            worker.start()
            time.sleep(0.05)
            copilot.stop()
            worker.join(timeout=2)
            self.assertFalse(worker.is_alive())
        finally:
            console_main.time.sleep = orig_sleep


if __name__ == "__main__":
    unittest.main()
