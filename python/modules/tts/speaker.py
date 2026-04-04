# -*- coding: utf-8 -*-
"""
TTS module — offline text-to-speech output.

Backend hierarchy (first available wins):
  1. pyttsx3   — fully offline, cross-platform (Windows SAPI5, macOS NSSpeech, Linux espeak)
  2. fallback  — logs the text to the console, no audio; agent continues without TTS

Usage:
    from tts.speaker import Speaker
    speaker = Speaker()
    speaker.say("Hello, world!")
    speaker.say_async("Non-blocking speech")
    speaker.stop()
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# ── Backend probe ─────────────────────────────────────────────────────────────

_BACKEND: str = "none"


def _probe_backends() -> str:
    try:
        import pyttsx3  # noqa: F401
        return "pyttsx3"
    except Exception:
        pass

    logger.warning(
        "TTS: pyttsx3 not available. Install: pip install pyttsx3. "
        "Agent will log responses to console instead of speaking."
    )
    return "none"


_BACKEND = _probe_backends()


# ── Speaker ───────────────────────────────────────────────────────────────────

class Speaker:
    """
    Wraps the available TTS backend with a simple say() / say_async() interface.

    Thread-safe: a single background worker serialises all speech requests so
    overlapping calls don't corrupt the underlying engine state.
    """

    def __init__(
        self,
        rate: int = 180,
        volume: float = 1.0,
        voice_index: Optional[int] = None,
    ) -> None:
        self._rate = rate
        self._volume = volume
        self._voice_index = voice_index
        self._engine = None
        self._lock = threading.Lock()
        self._queue: list[str] = []
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._work_event = threading.Event()
        self._enabled = (_BACKEND != "none")

        if self._enabled:
            self._init_engine()
            self._start_worker()

    # ── Engine lifecycle ──────────────────────────────────────────────────────

    def _init_engine(self) -> None:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", self._rate)
            engine.setProperty("volume", max(0.0, min(1.0, self._volume)))
            if self._voice_index is not None:
                voices = engine.getProperty("voices")
                if voices and 0 <= self._voice_index < len(voices):
                    engine.setProperty("voice", voices[self._voice_index].id)
            self._engine = engine
            logger.info("TTS: pyttsx3 engine initialised (rate=%d, volume=%.2f)", self._rate, self._volume)
        except Exception as exc:
            logger.warning("TTS: pyttsx3 engine init failed: %s. Falling back to console.", exc)
            self._enabled = False
            self._engine = None

    def _start_worker(self) -> None:
        self._stop_event.clear()
        t = threading.Thread(target=self._worker, daemon=True, name="tts-worker")
        t.start()
        self._worker_thread = t

    def _worker(self) -> None:
        while not self._stop_event.is_set():
            self._work_event.wait(timeout=1.0)
            self._work_event.clear()
            while True:
                with self._lock:
                    if not self._queue:
                        break
                    text = self._queue.pop(0)
                self._speak_sync(text)

    def _speak_sync(self, text: str) -> None:
        if not text:
            return
        if self._engine is None:
            print(f"[TTS] {text}")
            return
        try:
            self._engine.say(text)
            self._engine.runAndWait()
        except Exception as exc:
            logger.debug("TTS speak failed: %s", exc)
            print(f"[TTS] {text}")

    # ── Public API ────────────────────────────────────────────────────────────

    def say(self, text: str) -> None:
        """Speak *text* synchronously (blocks until finished)."""
        if not text:
            return
        if not self._enabled:
            print(f"[TTS] {text}")
            return
        self._speak_sync(text)

    def say_async(self, text: str) -> None:
        """Queue *text* for async speech (returns immediately)."""
        if not text:
            return
        if not self._enabled:
            print(f"[TTS] {text}")
            return
        with self._lock:
            self._queue.append(text)
        self._work_event.set()

    def stop(self) -> None:
        """Stop the worker thread and release TTS resources."""
        self._stop_event.set()
        self._work_event.set()
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=3.0)
            self._worker_thread = None
        if self._engine is not None:
            try:
                self._engine.stop()
            except Exception:
                pass
            self._engine = None

    @property
    def enabled(self) -> bool:
        """True if a real TTS backend is available."""
        return self._enabled

    def backend_name(self) -> str:
        return _BACKEND
