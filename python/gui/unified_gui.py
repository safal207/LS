import sys
import os
import queue
import threading
import logging
import time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal

# === LOGGING CONFIG ===
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("UnifiedGUI")

# === PATH HACK ===
current_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if current_root not in sys.path:
    sys.path.append(current_root)

try:
    from audio_module import AudioIngestion
    from stt_module import SpeechToText
    from python.modules.adaptive_brain import AdaptiveBrain
    from python.modules.self_improving import SelfImprovingBrain
    from python.modules.hexagon_core.lpi import LPI
    from python.rust_bridge import RustOptimizer
except ImportError as e:
    logger.critical(f"CRITICAL MODULE ERROR: {e}")
    sys.exit(1)

class GhostCore(QObject):
    """
    Bridge between Worker Threads and GUI.
    Implements L-THREAD Safety Protocol (Graceful Shutdown).
    """
    new_answer = pyqtSignal(str, str, str) # question, answer, mode
    status_update = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        # Communication Channels
        self.audio_queue = queue.Queue()
        self.text_queue = queue.Queue()

        # Lifecycle Control
        self._stop_event = threading.Event()
        self.threads = []

        # Resources
        self.rust_optimizer = RustOptimizer()

        # === BRAIN INITIALIZATION (SOVEREIGN EDITION) ===
        # tier="local" -> Только Qwen (бесплатно, приватно)
        # tier="cloud" -> DeepSeek API (дешево, мощно)
        self.brain = AdaptiveBrain(
            tier="local",
            # Вставь сюда ключ DeepSeek, если захочешь использовать Cloud tier
            api_keys={"deepseek": "sk-YOUR-DEEPSEEK-KEY"},
            rust_instance=self.rust_optimizer
        )

        # Modules
        self.audio_module = AudioIngestion(self.audio_queue)
        self.stt_module = SpeechToText(self.audio_queue, self.text_queue)
        self.learner = SelfImprovingBrain(rust_instance=self.rust_optimizer)

    def start(self):
        """Starts all subsystems in daemon threads but keeps ref for joining."""
        if not self._stop_event.is_set():
            self._stop_event.clear()

        logger.info("Starting GhostCore Subsystems...")

        # 1. Audio Thread
        t_audio = threading.Thread(target=self.audio_module.run, daemon=True, name="AudioThread")
        t_audio.start()
        self.threads.append(t_audio)

        # 2. STT Thread
        t_stt = threading.Thread(target=self.stt_module.run, daemon=True, name="STTThread")
        t_stt.start()
        self.threads.append(t_stt)

        # 3. Brain Processing Thread
        t_proc = threading.Thread(target=self._process_loop, daemon=True, name="BrainThread")
        t_proc.start()
        self.threads.append(t_proc)

        self.status_update.emit("GhostCore Active (Sovereign Mode)")

    def stop(self):
        """Graceful shutdown sequence."""
        logger.info("Initiating Shutdown Sequence...")
        self.status_update.emit("Stopping...")

        self._stop_event.set()

        if hasattr(self.audio_module, 'stop'): self.audio_module.stop()
        if hasattr(self.stt_module, 'stop'): self.stt_module.stop()

        for t in self.threads:
            if t.is_alive():
                t.join(timeout=1.0)
                if t.is_alive():
                    logger.warning(f"Thread {t.name} did not terminate gracefully.")

        self.rust_optimizer.close()
        self.status_update.emit("GhostCore Offline")
        logger.info("Shutdown Complete.")

    def _process_loop(self):
        """Main Cognitive Loop."""
        logger.info("Brain Loop Started.")
        while not self._stop_event.is_set():
            try:
                item = self.text_queue.get(timeout=0.5)

                if item['type'] == 'question':
                    question = item['text']
                    timestamp = item['timestamp']

                    self.status_update.emit("Thinking...")
                    logger.info(f"Processing: {question[:30]}...")

                    try:
                        answer = self.brain.generate(question)
                    except Exception as e:
                        logger.error(f"Brain Error: {e}")
                        answer = "Error: Cognitive module failure."

                    self.new_answer.emit(question, answer, self.brain.tier)

                    try:
                        self.learner.learn_from_session([{
                            'question': question,
                            'answer': answer,
                            'timestamp': timestamp
                        }])
                    except Exception as e:
                        logger.error(f"Learning Error: {e}")

                self.text_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Loop Exception: {e}")
                time.sleep(1)

class GhostApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.gui = LPI()
        self.core = GhostCore()

        self.core.new_answer.connect(self.gui.update_ui)
        self.core.status_update.connect(self.gui.set_status)
        self.gui.btn_close.clicked.connect(self.shutdown)

        import signal
        signal.signal(signal.SIGINT, lambda *args: self.shutdown())

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
