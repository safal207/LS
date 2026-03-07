from __future__ import annotations

import logging
from typing import List

import numpy as np

from .frame_buffer import AudioRingBuffer
from .pipeline import LinearResampler

logger = logging.getLogger(__name__)

try:
    import audio_core as _audio_core  # type: ignore
except Exception as exc:  # pragma: no cover
    _audio_core = None
    logger.info("Rust audio_core unavailable, using Python fallback: %s", exc)


class RustAudioCore:
    """Rust DSP facade with transparent Python fallback."""

    def __init__(self, capacity_samples: int = 16000 * 10):
        self._resampler = LinearResampler()
        if _audio_core is not None and hasattr(_audio_core, "RustAudioCore"):
            self._impl = _audio_core.RustAudioCore(capacity_samples)
            self._fallback = None
        else:
            self._impl = None
            self._fallback = AudioRingBuffer(capacity_samples=capacity_samples)

    def push_audio(self, samples: np.ndarray) -> int:
        if samples.dtype != np.int16:
            samples = samples.astype(np.int16, copy=False)
        if self._impl is not None:
            return int(self._impl.push_audio(samples.tobytes()))
        return int(self._fallback.push(samples))

    def read_frames(self, frame_samples: int, max_frames: int = 32) -> List[np.ndarray]:
        if self._impl is not None:
            chunks_bytes = self._impl.read_frames(int(frame_samples), int(max_frames))
            return [np.frombuffer(chunk, dtype=np.int16).copy() for chunk in chunks_bytes]

        out: List[np.ndarray] = []
        for _ in range(max_frames):
            if self._fallback.available_samples() < frame_samples:
                break
            out.append(self._fallback.pop(frame_samples))
        return out

    def resample(self, samples: np.ndarray, in_rate: int, out_rate: int) -> np.ndarray:
        if samples.dtype != np.int16:
            samples = samples.astype(np.int16, copy=False)
        if self._impl is not None:
            out = self._impl.resample(samples.tolist(), int(in_rate), int(out_rate))
            return np.asarray(out, dtype=np.int16)
        return self._resampler.resample(samples, in_rate, out_rate)
