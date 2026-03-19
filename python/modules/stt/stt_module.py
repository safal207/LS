#!/usr/bin/env python3
"""
Speech-to-Text Module (Module 2: STT Processing)
Processes audio files using Faster-Whisper and detects questions.
Returns N-best hypotheses with per-segment confidence scores.
"""

import math
import threading
import time
import logging
import queue
import os
from typing import Optional, List, Dict, Any
from faster_whisper import WhisperModel
from config import WHISPER_MODEL_SIZE
from shared.utils import is_question

logger = logging.getLogger(__name__)

class SpeechToText:
    def __init__(self, input_queue: queue.Queue, output_queue: queue.Queue):
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.model = None
        self.running = False
        self.current_sentence = ""  # Buffer for accumulating speech
        
    def load_model(self) -> bool:
        """Load Whisper model"""
        try:
            logger.info(f"Loading Whisper model: {WHISPER_MODEL_SIZE}")
            
            # Load model with CPU optimizations for Ryzen 5700U
            self.model = WhisperModel(
                WHISPER_MODEL_SIZE,
                device="cpu",
                compute_type="int8",  # Use int8 quantization for CPU
                cpu_threads=4,  # Limit threads to avoid overloading
                num_workers=2
            )
            
            logger.info("Whisper model loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            return False
    
    def transcribe_audio(self, audio_file: str) -> List[Dict[str, Any]]:
        “””Transcribe audio file and return N-best hypotheses with confidence scores.

        Returns a list of hypothesis dicts: ``[{“text”: str, “confidence”: float}]``.
        Each hypothesis corresponds to one Whisper segment.  ``confidence`` is
        derived from ``segment.avg_logprob`` mapped to ``[0, 1]`` via ``math.exp``.
        Returns an empty list on failure.
        “””
        try:
            if not self.model:
                logger.error(“Model not loaded”)
                return []

            logger.debug(f”Transcribing: {audio_file}”)

            # Transcribe with optimized settings — beam_size=5 already produces
            # rich per-segment scores we can surface as N-best hypotheses.
            segments, info = self.model.transcribe(
                audio_file,
                beam_size=5,
                best_of=5,
                patience=1.0,
                length_penalty=1.0,
                temperature=0.0,  # Deterministic for consistency
                compression_ratio_threshold=2.4,
                log_prob_threshold=-1.0,
                no_speech_threshold=0.6,
                condition_on_previous_text=True,
                initial_prompt=None,
                prefix=None,
                suppress_blank=True,
                suppress_tokens=[-1],
                without_timestamps=True,
                max_initial_timestamp=1.0,
                word_timestamps=False,
                prepend_punctuations=”\”'”¿([{-”,
                append_punctuations=”\”'.。,，!！?？:：”)]}、”
            )

            hypotheses: List[Dict[str, Any]] = []
            for segment in segments:
                text = segment.text.strip()
                if not text:
                    continue
                # avg_logprob is in (-inf, 0]; exp() maps it to (0, 1]
                confidence = math.exp(max(segment.avg_logprob, -10.0))
                hypotheses.append({“text”: text, “confidence”: round(confidence, 4)})

            if hypotheses:
                logger.debug(f”Hypotheses: {hypotheses}”)

            return hypotheses

        except Exception as e:
            logger.error(f”Transcription error for {audio_file}: {e}”)
            return []
        finally:
            # Clean up temporary file
            try:
                if os.path.exists(audio_file):
                    os.unlink(audio_file)
            except Exception as e:
                logger.warning(f”Failed to delete temp file {audio_file}: {e}”)
    
    def process_hypotheses(self, hypotheses: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Accumulate hypotheses into sentence buffer; emit when question detected.

        Returns ``{"hypotheses": list, "text": str}`` when a complete question is
        buffered, otherwise ``None``.  The best hypothesis (highest confidence) is
        used to accumulate the sentence buffer; all hypotheses are forwarded so that
        SmartEar can run its own selection logic.
        """
        if not hypotheses:
            return None

        # Pick the hypothesis with highest confidence as the representative text
        best = max(hypotheses, key=lambda h: h["confidence"])
        transcript = best["text"]

        self.current_sentence += " " + transcript
        self.current_sentence = self.current_sentence.strip()

        logger.debug(f"Current buffer: {self.current_sentence}")

        if is_question(self.current_sentence):
            logger.info(f"Question detected: {self.current_sentence}")
            question = self.current_sentence
            self.current_sentence = ""
            return {"text": question, "hypotheses": hypotheses}

        if len(self.current_sentence) > 500:
            logger.debug("Buffer too long, resetting")
            self.current_sentence = ""

        return None

    def process_transcript(self, transcript: str) -> Optional[str]:
        """Legacy helper kept for backward-compatibility.  Prefer process_hypotheses."""
        if not transcript:
            return None
        self.current_sentence += " " + transcript
        self.current_sentence = self.current_sentence.strip()
        if is_question(self.current_sentence):
            question = self.current_sentence
            self.current_sentence = ""
            return question
        if len(self.current_sentence) > 500:
            self.current_sentence = ""
        return None
    
    def run(self):
        """Main STT processing loop"""
        logger.info("Starting Speech-to-Text module")
        
        # Load model first
        if not self.load_model():
            logger.error("Failed to load STT model, exiting")
            return
        
        self.running = True

        try:
            while self.running:
                try:
                    # Get audio file from queue (non-blocking)
                    audio_file = self.input_queue.get(timeout=1.0)

                    # Transcribe audio — returns N-best hypotheses
                    start_time = time.time()
                    hypotheses = self.transcribe_audio(audio_file)
                    transcription_time = time.time() - start_time

                    logger.debug(f"Transcription took {transcription_time:.2f}s")

                    # Process hypotheses for questions
                    result = self.process_hypotheses(hypotheses)

                    if result:
                        try:
                            self.output_queue.put_nowait({
                                'type': 'question',
                                'text': result['text'],
                                'hypotheses': result['hypotheses'],
                                'timestamp': time.time(),
                            })
                            logger.info(f"Sent question to queue: {result['text']}")
                        except queue.Full:
                            logger.warning("Output queue full, dropping question")

                    self.input_queue.task_done()
                    
                except queue.Empty:
                    # No audio files to process, continue loop
                    continue
                except Exception as e:
                    logger.error(f"STT processing error: {e}")
                    
        except KeyboardInterrupt:
            logger.info("STT module interrupted")
        except Exception as e:
            logger.error(f"STT module error: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop STT module"""
        logger.info("Stopping Speech-to-Text module")
        self.running = False
        
        # Clear queues
        while not self.input_queue.empty():
            try:
                self.input_queue.get_nowait()
            except queue.Empty:
                break
                
        logger.info("Speech-to-Text module stopped")

# Test function
def test_stt_module():
    """Test STT module with sample audio"""
    import queue
    import numpy as np
    import soundfile as sf
    import tempfile
    
    # Create test queues
    input_queue = queue.Queue()
    output_queue = queue.Queue()
    
    # Create test audio file
    test_audio = np.random.randn(16000).astype(np.float32) * 0.1  # 1 second of noise
    temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    temp_filename = temp_file.name
    temp_file.close()
    
    sf.write(temp_filename, test_audio, 16000)
    
    # Create and start STT module
    stt_module = SpeechToText(input_queue, output_queue)
    
    print("Testing STT module...")
    
    # Put test file in queue
    input_queue.put(temp_filename)
    
    # Start module in separate thread
    stt_thread = threading.Thread(target=stt_module.run)
    stt_thread.start()
    
    # Wait a bit
    time.sleep(5)
    
    # Stop module
    stt_module.stop()
    stt_thread.join()
    
    # Check results
    if not output_queue.empty():
        result = output_queue.get()
        print(f"Result: {result}")
    else:
        print("No results (expected for noise audio)")

if __name__ == "__main__":
    test_stt_module()