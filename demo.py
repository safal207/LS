#!/usr/bin/env python3
"""
Simulation mode for testing without audio hardware
Simulates interview scenarios for testing the pipeline
"""

import time
import threading
import queue
import logging
from typing import List

from stt_module import SpeechToText
from llm_module import LanguageModel
from config import SYSTEM_PROMPT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimulationMode:
    def __init__(self):
        self.transcribe_queue = queue.Queue()
        self.llm_queue = queue.Queue()
        self.ui_queue = queue.Queue()
        
        # Initialize modules
        self.stt_module = SpeechToText(self.transcribe_queue, self.llm_queue)
        self.llm_module = LanguageModel(self.llm_queue, self.ui_queue)
        
        self.running = False
    
    def simulate_audio_input(self, test_phrases: List[str]):
        """Simulate audio input by putting text directly into STT queue"""
        logger.info("Starting simulation mode...")
        
        # Start modules
        stt_thread = threading.Thread(target=self.stt_module.run, daemon=True)
        llm_thread = threading.Thread(target=self.llm_module.run, daemon=True)
        ui_thread = threading.Thread(target=self.ui_display_loop, daemon=True)
        
        stt_thread.start()
        llm_thread.start()
        ui_thread.start()
        
        # Simulate interview dialogue
        for i, phrase in enumerate(test_phrases):
            logger.info(f"Simulating phrase {i+1}: {phrase}")
            
            # Put phrase in queue as if it came from audio transcription
            try:
                self.llm_queue.put_nowait({
                    'type': 'question',
                    'text': phrase,
                    'timestamp': time.time()
                })
            except queue.Full:
                logger.warning("Queue full, skipping phrase")
            
            # Wait between phrases
            time.sleep(2)
        
        # Let processing finish
        time.sleep(5)
        
        self.stop()
    
    def ui_display_loop(self):
        """Display responses in console"""
        while self.running:
            try:
                response = self.ui_queue.get(timeout=1)
                print(f"\n{'='*60}")
                print("🎙️  INTERVIEWER ASKED:")
                print(f"   {response.get('question', '')}")
                print(f"{'='*60}")
                print("💡 SUGGESTED ANSWER:")
                print(f"   {response.get('response', '')}")
                print(f"{'='*60}")
                print(f"⏱️  Generation time: {response.get('generation_time', 0):.2f}s")
                print()
                self.ui_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"UI display error: {e}")
    
    def run_demo(self):
        """Run a demonstration interview simulation"""
        logger.info("Starting Interview Copilot Demo")
        print("\n" + "="*60)
        print("🤖 LOCAL INTERVIEW COPILOT - DEMO MODE")
        print("="*60)
        print("System Prompt:")
        print(f"   {SYSTEM_PROMPT}")
        print("="*60)
        print()
        
        # Test interview dialogue
        test_dialogue = [
            "Расскажите о вашем опыте с React?",
            "Какие жизненные циклы компонентов вы знаете?",
            "В чем разница между useState и useEffect?",
            "Как вы оптимизируете производительность React приложений?",
            "Почему важно использовать ключи в списках?",
            "Объясните концепцию Virtual DOM"
        ]
        
        self.running = True
        self.simulate_audio_input(test_dialogue)
    
    def stop(self):
        """Stop simulation"""
        logger.info("Stopping simulation")
        self.running = False
        self.stt_module.stop()
        self.llm_module.stop()

def main():
    """Main demo function"""
    print("Interview Copilot - Simulation Demo")
    print("This will test the STT and LLM modules without audio input")
    print()
    
    sim = SimulationMode()
    
    try:
        sim.run_demo()
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
        sim.stop()
    except Exception as e:
        print(f"\nDemo error: {e}")
        sim.stop()

if __name__ == "__main__":
    main()