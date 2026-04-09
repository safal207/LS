#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Speech-to-Text Module (Module 2: STT Processing)
Processes audio files using Faster-Whisper.

Key improvements over the original:
* ``word_timestamps=True`` — each word carries a ``probability`` score so that
  SmartEar's PhoneticCorrector can target only uncertain words instead of
  blindly correcting everything.
* ``initial_prompt`` — seeded with IT domain vocabulary so Whisper already
  produces "React" instead of "реак" for well-known terms.  The prompt is
  updated dynamically from the last recognised question.
* Output format carries ``_words`` (list of {word, probability}) alongside the
  plain ``text``, giving SmartEar structured confidence data.
"""

import math
import threading
import time
import logging
import queue
import os
from typing import List, Dict, Any, Optional

from faster_whisper import WhisperModel
from config import WHISPER_MODEL_SIZE
from shared.operator_schema import OperatorUtterance, ensure_operator_item
from shared.utils import is_question

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Domain-seeded initial prompt for Whisper
# Significantly improves recognition of IT terminology out of the box.
# ---------------------------------------------------------------------------
_BASE_INITIAL_PROMPT = (
    "Разговор об IT: React, TypeScript, JavaScript, Vue, Angular, Next.js, "
    "Docker, Kubernetes, Python, FastAPI, Django, Node.js, REST, GraphQL, "
    "PostgreSQL, Redis, CI/CD, GitHub, микросервисы, деплой, рефакторинг, "
    "API, SDK, ORM, pipeline, debugging, коммит, ветка, репозиторий."
)


class SpeechToText:
    def __init__(self, input_queue: queue.Queue, output_queue: queue.Queue):
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.model: Optional[WhisperModel] = None
        self.running = False
        self.current_sentence = ""           # sentence accumulation buffer
        self._current_words: List[dict] = [] # per-word data for current buffer
        self._current_log_probs: List[float] = []  # raw log_probs across chunks
        # Dynamic prompt: updated with each committed question so the next chunk
        # benefits from recent vocabulary.
        self._dynamic_prompt: str = _BASE_INITIAL_PROMPT

    def load_model(self) -> bool:
        """Load Whisper model with CPU optimisations for Ryzen 5700U."""
        try:
            logger.info(f"Loading Whisper model: {WHISPER_MODEL_SIZE}")
            self.model = WhisperModel(
                WHISPER_MODEL_SIZE,
                device="cpu",
                compute_type="int8",
                cpu_threads=4,
                num_workers=2,
            )
            logger.info("Whisper model loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            return False

    # ------------------------------------------------------------------
    # Transcription
    # ------------------------------------------------------------------

    def transcribe_audio(self, audio_file: str) -> Dict[str, Any]:
        """Transcribe *audio_file* and return structured output.

        Returns a dict::

            {
                "text": str,               # joined transcript
                "words": [                 # per-word data (empty if unavailable)
                    {"word": str, "probability": float},
                    ...
                ],
                "asr_confidence": float,   # exp(avg_logprob) averaged over segments
            }

        Returns an empty dict on failure.
        """
        try:
            if not self.model:
                logger.error("Model not loaded")
                return {}

            logger.debug(f"Transcribing: {audio_file}")

            segments, _info = self.model.transcribe(
                audio_file,
                beam_size=5,
                temperature=0.0,
                compression_ratio_threshold=2.4,
                log_prob_threshold=-1.0,
                no_speech_threshold=0.6,
                condition_on_previous_text=True,
                initial_prompt=self._dynamic_prompt,
                suppress_blank=True,
                suppress_tokens=[-1],
                without_timestamps=False,   # needed for word_timestamps
                word_timestamps=True,       # gives per-word probability
            )

            text_parts: List[str] = []
            words_out: List[dict] = []
            chunk_log_probs: List[float] = []

            for segment in segments:
                seg_text = segment.text.strip()
                if not seg_text:
                    continue
                text_parts.append(seg_text)
                chunk_log_probs.append(segment.avg_logprob)

                # Collect per-word data when available
                if segment.words:
                    for w in segment.words:
                        word_str = w.word.strip()
                        if word_str:
                            words_out.append({
                                "word": word_str,
                                "probability": round(float(w.probability), 4),
                            })

            if not text_parts:
                return {}

            transcript = " ".join(text_parts)

            result = {
                "text": transcript,
                "words": words_out,
                # Return raw log_probs so process_result can accumulate them
                # across chunks before computing final asr_confidence.
                "_chunk_log_probs": chunk_log_probs,
            }
            avg_lp = sum(chunk_log_probs) / len(chunk_log_probs) if chunk_log_probs else -10.0
            logger.debug("Transcription: %r (logprob=%.3f, words=%d)",
                         transcript, avg_lp, len(words_out))
            return result

        except Exception as e:
            logger.error(f"Transcription error for {audio_file}: {e}")
            return {}
        finally:
            try:
                if os.path.exists(audio_file):
                    os.unlink(audio_file)
            except Exception as e:
                logger.warning(f"Failed to delete temp file {audio_file}: {e}")

    # ------------------------------------------------------------------
    # Sentence buffering & question detection
    # ------------------------------------------------------------------

    def process_result(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Accumulate transcription into sentence buffer; emit on question detection.

        Returns a queue item dict when a complete question is buffered, else None.
        The item carries the plain ``text``, per-word ``_words``, and raw
        ``_asr_confidence`` so SmartEar can apply targeted phonetic correction.
        """
        if not result:
            return None

        transcript: str = result.get("text", "").strip()
        if not transcript:
            return None

        words: List[dict] = result.get("words", [])
        chunk_log_probs: List[float] = result.get("_chunk_log_probs", [])

        self.current_sentence = (self.current_sentence + " " + transcript).strip()
        self._current_words.extend(words)
        self._current_log_probs.extend(chunk_log_probs)

        logger.debug(f"Buffer: {self.current_sentence!r}")

        if is_question(self.current_sentence):
            logger.info(f"Question detected: {self.current_sentence!r}")
            question = self.current_sentence
            buffered_words = list(self._current_words)

            # Average log_probs across ALL chunks that formed this question,
            # then convert to confidence — more accurate than using last chunk.
            if self._current_log_probs:
                avg_logprob = sum(self._current_log_probs) / len(self._current_log_probs)
                asr_confidence = round(math.exp(max(avg_logprob, -10.0)), 4)
            else:
                asr_confidence = 0.0

            # Update dynamic prompt with latest question context
            self._dynamic_prompt = _BASE_INITIAL_PROMPT + "  " + question[:200]

            # Reset buffers
            self.current_sentence = ""
            self._current_words = []
            self._current_log_probs = []

            utterance = OperatorUtterance(
                type="question",
                text=question,
                confidence=asr_confidence,
                source="local_stt",
                words=buffered_words,
                clean_text=question,
                timestamp=time.time(),
            )
            return ensure_operator_item(utterance, default_source="local_stt")

        # Safety valve: prevent unbounded buffer growth
        if len(self.current_sentence) > 500:
            logger.debug("Buffer overflow, resetting")
            self.current_sentence = ""
            self._current_words = []
            self._current_log_probs = []

        return None

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        logger.info("Starting Speech-to-Text module")

        if not self.load_model():
            logger.error("Failed to load STT model, exiting")
            return

        self.running = True

        try:
            while self.running:
                try:
                    audio_file = self.input_queue.get(timeout=1.0)

                    start_time = time.time()
                    result = self.transcribe_audio(audio_file)
                    transcription_time = time.time() - start_time
                    logger.debug(f"Transcription took {transcription_time:.2f}s")

                    item = self.process_result(result)

                    if item is not None:
                        try:
                            self.output_queue.put_nowait(item)
                            logger.info(f"Sent question to SmartEar queue: {item['text']!r}")
                        except queue.Full:
                            logger.warning("Output queue full, dropping question")

                    self.input_queue.task_done()

                except queue.Empty:
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
        logger.info("Stopping Speech-to-Text module")
        self.running = False
        while not self.input_queue.empty():
            try:
                self.input_queue.get_nowait()
            except queue.Empty:
                break
        logger.info("Speech-to-Text module stopped")


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

def test_stt_module():
    import numpy as np
    import soundfile as sf
    import tempfile

    input_queue: queue.Queue = queue.Queue()
    output_queue: queue.Queue = queue.Queue()

    test_audio = np.random.randn(16000).astype(np.float32) * 0.1
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(tmp.name, test_audio, 16000)
    tmp.close()

    stt = SpeechToText(input_queue, output_queue)
    print("Testing STT module…")
    input_queue.put(tmp.name)

    t = threading.Thread(target=stt.run)
    t.start()
    time.sleep(5)
    stt.stop()
    t.join()

    if not output_queue.empty():
        print(f"Result: {output_queue.get()}")
    else:
        print("No results (expected for noise audio)")


if __name__ == "__main__":
    test_stt_module()
