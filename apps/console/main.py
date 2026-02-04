#!/usr/bin/env python3
"""
Local Interview Copilot - Console MVP
Phase 1: Audio capture -> STT -> LLM -> Console output
"""

from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from shared.config_loader import load_config

os.environ.setdefault("LS_APP", "console")
cfg = load_config("console")


import threading
import queue
import time
import logging
from typing import Optional

from audio_module import AudioIngestion
from stt_module import SpeechToText
from llm_module import LanguageModel
from utils import check_system_resources

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class InterviewCopilot:
    def __init__(self):
        self.transcribe_queue = queue.Queue(maxsize=10)
        self.llm_queue = queue.Queue(maxsize=10)  # Queue for questions to LLM
        self.ui_queue = queue.Queue(maxsize=10)
        
        # Check system resources before starting
        if not check_system_resources():
            logger.warning("System resources may be insufficient!")
        
        # Initialize modules
        self.audio_module = AudioIngestion(self.transcribe_queue)
        self.stt_module = SpeechToText(self.transcribe_queue, self.llm_queue)
        self.llm_module = LanguageModel(self.llm_queue, self.ui_queue)
        
        self.running = False
        
    def start(self):
        """Start all modules in separate threads"""
        logger.info("Starting Interview Copilot...")
        
        self.running = True
        
        # Start threads
        audio_thread = threading.Thread(target=self.audio_module.run, daemon=True)
        stt_thread = threading.Thread(target=self.stt_module.run, daemon=True)
        llm_thread = threading.Thread(target=self.llm_module.run, daemon=True)
        ui_thread = threading.Thread(target=self._ui_display_loop, daemon=True)
        
        audio_thread.start()
        stt_thread.start()
        llm_thread.start()
        ui_thread.start()
        
        logger.info("All modules started. Press Ctrl+C to stop.")
        
        try:
            # Keep main thread alive
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            self.stop()
            
    def stop(self):
        """Stop all modules"""
        self.running = False
        self.audio_module.stop()
        self.stt_module.stop()
        self.llm_module.stop()
        
    def _ui_display_loop(self):
        """Display responses in console"""
        while self.running:
            try:
                response = self.ui_queue.get(timeout=1)
                print(f"\n{'='*50}")
                print("💡 SUGGESTED ANSWER:")
                print(f"{'='*50}")
                print(response)
                print(f"{'='*50}\n")
                self.ui_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"UI display error: {e}")

def main():
    copilot = InterviewCopilot()
    copilot.start()

if __name__ == "__main__":
    main()
