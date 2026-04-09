#!/usr/bin/env python3
"""
LS — Console Runtime
Audio capture -> STT -> LLM -> Console output
"""

from python.modules.shared.bootstrap import bootstrap_app

ctx = bootstrap_app(__file__, "console")
cfg = ctx.config


import threading
import queue
import time
import logging
from typing import Optional

from modules import config
from modules.agent.loop import AgentLoop
from modules.agent.sinks import build_event_sink
from modules.audio.audio_module import AudioIngestion
from modules.stt.stt_module import SpeechToText
from modules.stt.smart_ear import SmartEar
from modules.llm.llm_module import LanguageModel
from shared.utils import check_system_resources

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ConsoleRuntime:
    def __init__(self):
        self.transcribe_queue = queue.Queue(maxsize=10)
        # smart_ear_queue sits between STT output and AgentLoop input
        self.smart_ear_queue = queue.Queue(maxsize=10)
        self.llm_queue = queue.Queue(maxsize=10)  # Queue for questions to LLM
        self.ui_queue = queue.Queue(maxsize=10)

        # Check system resources before starting
        if not check_system_resources():
            logger.warning("System resources may be insufficient!")

        # Initialize modules
        # AudioIngestion now publishes VAD events to event_bus
        self.audio_module = AudioIngestion(
            self.transcribe_queue,
            event_bus=ctx.event_bus,
        )
        # STT now emits N-best hypotheses; its output goes to smart_ear_queue
        self.stt_module = SpeechToText(self.transcribe_queue, self.smart_ear_queue)
        self.llm_module = LanguageModel(self.llm_queue, self.ui_queue)
        ctx.services.register("llm", self.llm_module)
        ctx.services.register("memory", {})
        ctx.services.register("logger", logger)
        event_sink = None
        if config.AGENT_OBSERVABILITY_ENABLED:
            event_sink = build_event_sink(config.AGENT_EVENT_SINK)

        self.agent_loop = AgentLoop(
            self.llm_queue,
            self.ui_queue,
            llm=self.llm_module,
            temporal_enabled=config.TEMPORAL_ENABLED,
            cancel_on_new_input=config.AGENT_CANCEL_ON_NEW_INPUT,
            cancel_grace_ms=config.AGENT_CANCEL_GRACE_MS,
            memory_max_chars=config.AGENT_MEMORY_MAX_CHARS,
            metrics_enabled=config.AGENT_METRICS_ENABLED,
            observability_enabled=config.AGENT_OBSERVABILITY_ENABLED,
            event_sink=event_sink,
            event_bus=ctx.event_bus,
        ) if config.AGENT_ENABLED else None

        # SmartEar wired between STT output and AgentLoop input.
        # Borrows Amygdala and CausalMemory from AgentLoop when available.
        _amygdala = None
        _causal_memory = None
        _cognitive_flow = None
        if self.agent_loop is not None:
            _amygdala = getattr(
                getattr(self.agent_loop, "causal_transitions", None), "amygdala", None
            )
            _causal_memory = getattr(self.agent_loop, "causal_memory", None)
            _cognitive_flow = getattr(self.agent_loop, "cognitive_flow", None)

        self.smart_ear = SmartEar(
            self.smart_ear_queue,
            self.llm_queue,
            amygdala=_amygdala,
            causal_memory=_causal_memory,
            cognitive_flow=_cognitive_flow,
            event_bus=ctx.event_bus,
        )

        self.running = False
        
    def start(self):
        """Start all modules in separate threads"""
        logger.info("Starting LS console runtime...")
        
        self.running = True
        
        # Start threads
        audio_thread = threading.Thread(target=self.audio_module.run, daemon=True)
        stt_thread = threading.Thread(target=self.stt_module.run, daemon=True)
        smart_ear_thread = threading.Thread(target=self.smart_ear.run, daemon=True)
        llm_thread = threading.Thread(
            target=self.agent_loop.run if self.agent_loop else self.llm_module.run,
            daemon=True,
        )
        ui_thread = threading.Thread(target=self._ui_display_loop, daemon=True)

        audio_thread.start()
        stt_thread.start()
        smart_ear_thread.start()
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
        self.smart_ear.stop()
        if self.agent_loop:
            self.agent_loop.stop()
        else:
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
    runtime = ConsoleRuntime()
    runtime.start()

if __name__ == "__main__":
    main()
