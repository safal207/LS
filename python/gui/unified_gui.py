import sys
import os
import queue
import threading
import logging
import time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("UnifiedGUI")

# Add root to sys.path to access root modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    from audio_module import AudioIngestion
    from stt_module import SpeechToText
    from python.modules.adaptive_brain import AdaptiveBrain
    from python.modules.self_improving import SelfImprovingBrain
    from python.modules.hexagon_core.lpi import LPI
    from python.rust_bridge import RustOptimizer
except ImportError as e:
    logger.error(f"Failed to import modules: {e}")
    sys.exit(1)

class GhostCore(QObject):
    """Bridge between Worker Threads and GUI"""
    new_answer = pyqtSignal(str, str, str) # question, answer, mode
    status_update = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.audio_queue = queue.Queue()
        self.text_queue = queue.Queue()

        # Shared Rust Instance
        self.rust_optimizer = RustOptimizer()

        # Modules
        self.audio_module = AudioIngestion(self.audio_queue)
        self.stt_module = SpeechToText(self.audio_queue, self.text_queue)
        self.brain = AdaptiveBrain(tier="free", rust_instance=self.rust_optimizer)
        self.learner = SelfImprovingBrain(rust_instance=self.rust_optimizer)

        self.running = False
        self.processing_thread = None

    def start(self):
        self.running = True

        # Start Audio & STT in their own threads
        threading.Thread(target=self.audio_module.run, daemon=True).start()
        threading.Thread(target=self.stt_module.run, daemon=True).start()

        # Start Brain Processing Loop
        self.processing_thread = threading.Thread(target=self._process_loop, daemon=True)
        self.processing_thread.start()

        self.status_update.emit("GhostCore Started (Rust + Python)")

    def stop(self):
        self.running = False
        self.audio_module.stop()
        self.stt_module.stop()
        self.status_update.emit("GhostCore Stopped")
        self.rust_optimizer.close()

    def _process_loop(self):
        while self.running:
            try:
                # Wait for question from STT
                item = self.text_queue.get(timeout=1.0)
                if item['type'] == 'question':
                    question = item['text']
                    timestamp = item['timestamp']

                    self.status_update.emit("Thinking...")

                    # Generate Answer
                    answer = self.brain.generate(question)

                    # Emit to GUI
                    self.new_answer.emit(question, answer, self.brain.tier)

                    # Learn in background
                    self.learner.learn_from_session([{
                        'question': question,
                        'answer': answer,
                        'timestamp': timestamp
                    }])

                self.text_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in process loop: {e}")

class GhostApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.gui = LPI()
        self.core = GhostCore()

        # Connect Signals
        self.core.new_answer.connect(self.gui.update_ui)
        self.core.status_update.connect(self.gui.set_status)
        self.gui.btn_close.clicked.connect(self.shutdown)

        # Start Core
        self.core.start()
        self.gui.show()

    def run(self):
        sys.exit(self.app.exec())

    def shutdown(self):
        self.core.stop()
        self.app.quit()

if __name__ == "__main__":
    app = GhostApp()
    app.run()
