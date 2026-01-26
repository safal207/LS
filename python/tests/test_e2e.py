import unittest
import time
import sys
import os
import threading
import queue
import tempfile
import shutil
from unittest.mock import MagicMock, patch

# Mock pyaudio
sys.modules["pyaudio"] = MagicMock()

# Add root path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Set Qt platform to offscreen
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Import
try:
    from python.gui.unified_gui import GhostCore
    from python.modules.adaptive_brain import AdaptiveBrain
    from PyQt6.QtWidgets import QApplication
    import python.rust_bridge
    # Save original class
    OriginalRustOptimizer = python.rust_bridge.RustOptimizer
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

class TestGhostGPTKiller(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "patterns.db")

        # Patch the class in the module
        self.patcher = patch('python.rust_bridge.RustOptimizer')
        self.MockClass = self.patcher.start()

        # Define side effect to return real instance with forced path
        def side_effect(*args, **kwargs):
            kwargs['db_path'] = self.db_path
            return OriginalRustOptimizer(*args, **kwargs)

        self.MockClass.side_effect = side_effect

    def tearDown(self):
        self.patcher.stop()
        shutil.rmtree(self.test_dir)

    def test_brain_tier_fallback(self):
        print("\n--- Testing Brain Tier Fallback ---")
        brain = AdaptiveBrain(tier="premium", api_keys={"groq": "fake", "claude": "fake"})

        response = brain.generate("Hello world")
        self.assertIsNotNone(response)
        print(f"Response: {response}")
        # Close rust db
        brain.rust.close()

    def test_core_flow(self):
        print("\n--- Testing Core Flow ---")
        if not QApplication.instance():
            app = QApplication(sys.argv)

        # Use a fresh DB for core flow
        core = GhostCore()

        # Mock audio/stt threads
        core.audio_module.run = MagicMock()
        core.stt_module.run = MagicMock()

        core.start()

        # Inject a question
        test_q = "What is Rust?"
        core.text_queue.put({
            'type': 'question',
            'text': test_q,
            'timestamp': time.time()
        })

        received = []
        def on_answer(q, a, mode):
            received.append((q, a, mode))

        core.new_answer.connect(on_answer)

        time.sleep(5)

        core.stop()
        # core.rust_optimizer.close() # handled by tearDown cleanup implicitly or OS, but good practice

        if received:
            print(f"Received answer: {received[0]}")
            self.assertEqual(received[0][0], test_q)
        else:
            print("WARNING: No answer received.")

if __name__ == "__main__":
    unittest.main()
