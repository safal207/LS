from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, Optional, Protocol

import numpy as np

from .endpoint_detector import EndpointDetector, SpeechSegment
from .frame_buffer import AudioRingBuffer
from .interfaces import IAudioCapture
from .vad import WebRTCVAD

logger = logging.getLogger(__name__)


@dataclass
class AudioMetrics:
    capture_latency_ms: float = 0.0
    vad_latency_ms: float = 0.0
    stt_latency_ms: float = 0.0
    agent_latency_ms: float = 0.0
    queue_drops: int = 0
    segments_emitted: int = 0


class EventLogger(Protocol):
    def __call__(self, event: str, **payload: float | int | str) -> None: ...


class LinearResampler:
    def resample(self, samples: np.ndarray, in_rate: int, out_rate: int) -> np.ndarray:
        if in_rate == out_rate:
            return samples
        if samples.size == 0:
            return samples.astype(np.int16, copy=False)

        x_old = np.linspace(0, 1, num=samples.size, endpoint=False)
        x_new = np.linspace(0, 1, num=int(samples.size * out_rate / in_rate), endpoint=False)
        y = np.interp(x_new, x_old, samples.astype(np.float32))
        return y.astype(np.int16)


class StreamingAudioPipeline:
    """Capture -> RingBuffer -> Resample -> 20ms framing -> VAD -> Endpoint."""

    def __init__(
        self,
        capture: IAudioCapture,
        *,
        input_rate: int = 16000,
        target_rate: int = 16000,
        frame_ms: int = 20,
        silence_ms_to_endpoint: int = 600,
        vad: Optional[WebRTCVAD] = None,
        ring_capacity_samples: int = 16000 * 10,
        thread_safe_buffer: bool = True,
        event_logger: EventLogger | None = None,
    ) -> None:
        self.capture = capture
        self.input_rate = int(input_rate)
        self.target_rate = int(target_rate)
        self.frame_ms = int(frame_ms)
        self.frame_samples = int(self.target_rate * self.frame_ms / 1000)
        self.vad = vad or WebRTCVAD()
        self.resampler = LinearResampler()
        self.endpoint = EndpointDetector(frame_ms=frame_ms, silence_ms_to_endpoint=silence_ms_to_endpoint)
        self.buffer = AudioRingBuffer(capacity_samples=ring_capacity_samples, thread_safe=thread_safe_buffer)
        self.metrics = AudioMetrics()
        self._frame_index = 0
        self._event_logger = event_logger

    def _emit(self, event: str, **payload: float | int | str) -> None:
        if self._event_logger is None:
            return
        try:
            self._event_logger(event, **payload)
        except Exception:
            logger.exception("event_logger failed for event=%s", event)

    def start(self) -> None:
        self.capture.start()

    def stop(self) -> None:
        self.capture.stop()

    def capture_step(self, num_samples: int = 1024) -> int:
        t0 = time.perf_counter()
        pcm = self.capture.read(num_samples)
        self.metrics.capture_latency_ms = (time.perf_counter() - t0) * 1000.0

        if self.input_rate != self.target_rate:
            pcm = self.resampler.resample(pcm, self.input_rate, self.target_rate)

        pushed = self.buffer.push(pcm)
        self.metrics.queue_drops = self.buffer.dropped_samples()
        self._emit(
            "capture",
            capture_latency_ms=round(self.metrics.capture_latency_ms, 3),
            pushed_samples=pushed,
            queue_drops=self.metrics.queue_drops,
        )
        return pushed

    def process_available_frames(self, on_segment: Callable[[SpeechSegment], None]) -> int:
        produced = 0
        while self.buffer.available_samples() >= self.frame_samples:
            frame = self.buffer.pop(self.frame_samples)
            frame_bytes = frame.astype(np.int16, copy=False).tobytes()

            t0 = time.perf_counter()
            speech = self.vad.is_speech(frame_bytes, self.target_rate)
            self.metrics.vad_latency_ms = (time.perf_counter() - t0) * 1000.0
            self._emit("vad", vad_latency_ms=round(self.metrics.vad_latency_ms, 3), speech=int(speech))

            segment = self.endpoint.process_frame(frame, speech, self._frame_index)
            self._frame_index += 1
            if segment is not None:
                on_segment(segment)
                produced += 1
                self.metrics.segments_emitted += 1
                self._emit("segment", samples=segment.samples.size, segments_emitted=self.metrics.segments_emitted)
        return produced
