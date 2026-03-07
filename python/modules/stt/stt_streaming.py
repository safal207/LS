from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import List

import numpy as np

try:
    from faster_whisper import WhisperModel
except Exception:
    WhisperModel = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class StreamingSTTResult:
    text: str
    latency_ms: float


@dataclass
class StreamingWhisperSTT:
    """Low-latency streaming wrapper around faster-whisper.

    Maintains a rolling context buffer (2-4s typical) to reduce boundary errors.
    """

    model_size: str = "small"
    sample_rate: int = 16000
    context_seconds: float = 3.0
    device: str = "cpu"
    compute_type: str = "int8"
    cpu_threads: int = 4
    num_workers: int = 2
    _model: WhisperModel | None = field(default=None, init=False)
    _context: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.int16), init=False)

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        if WhisperModel is None:
            raise RuntimeError("faster_whisper is not installed")
        self._model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
            cpu_threads=self.cpu_threads,
            num_workers=self.num_workers,
        )

    def _append_context(self, samples: np.ndarray) -> None:
        max_samples = int(self.sample_rate * self.context_seconds)
        merged = np.concatenate([self._context, samples]) if self._context.size else samples
        if merged.size > max_samples:
            merged = merged[-max_samples:]
        self._context = merged

    def transcribe_segment(self, samples: np.ndarray, language: str | None = None) -> StreamingSTTResult:
        self._ensure_model()
        if samples.dtype != np.int16:
            samples = samples.astype(np.int16, copy=False)

        self._append_context(samples)
        audio = self._context.astype(np.float32) / 32768.0

        t0 = time.perf_counter()
        segments, _ = self._model.transcribe(
            audio,
            language=language,
            beam_size=1,
            best_of=1,
            temperature=0.0,
            condition_on_previous_text=True,
            without_timestamps=True,
        )
        latency = (time.perf_counter() - t0) * 1000.0

        text = " ".join(s.text.strip() for s in segments if getattr(s, "text", "").strip()).strip()
        return StreamingSTTResult(text=text, latency_ms=latency)


class MockStreamingSTT:
    """Test double for pipeline tests without heavy model deps."""

    def __init__(self) -> None:
        self.calls: List[np.ndarray] = []

    def transcribe_segment(self, samples: np.ndarray, language: str | None = None) -> StreamingSTTResult:
        self.calls.append(samples.copy())
        return StreamingSTTResult(text=f"mock:{samples.size}", latency_ms=0.1)
