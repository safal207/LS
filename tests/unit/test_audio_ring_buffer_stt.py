from __future__ import annotations

import numpy as np

from python.modules.audio.endpoint_detector import SpeechSegment
from python.modules.audio.frame_buffer import AudioRingBuffer
from python.modules.audio.pipeline import StreamingAudioPipeline
from python.modules.stt.stt_streaming import MockStreamingSTT


class _DummyCapture:
    def __init__(self, chunks: list[np.ndarray]):
        self._chunks = chunks
        self._i = 0

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def read(self, num_samples: int) -> np.ndarray:
        if self._i >= len(self._chunks):
            return np.zeros(num_samples, dtype=np.int16)
        c = self._chunks[self._i]
        self._i += 1
        return c


def test_ring_buffer_overwrite_keeps_latest_samples() -> None:
    rb = AudioRingBuffer(capacity_samples=8)
    rb.push(np.arange(6, dtype=np.int16))
    rb.push(np.arange(6, 12, dtype=np.int16))

    out = rb.pop(8)
    assert out.tolist() == [4, 5, 6, 7, 8, 9, 10, 11]


def test_pipeline_segment_to_mock_stt() -> None:
    chunks = [np.full(1024, 5000, dtype=np.int16) for _ in range(8)] + [np.zeros(1024, dtype=np.int16) for _ in range(12)]
    pipeline = StreamingAudioPipeline(_DummyCapture(chunks), input_rate=16000, target_rate=16000)
    stt = MockStreamingSTT()

    segments: list[SpeechSegment] = []

    for _ in chunks:
        pipeline.capture_step(1024)
        pipeline.process_available_frames(segments.append)

    # Force flush tail in case endpoint threshold not reached inside loop
    flushed = pipeline.endpoint.flush(frame_index=999)
    if flushed is not None:
        segments.append(flushed)

    assert segments, "Expected at least one speech segment"

    result = stt.transcribe_segment(segments[0].samples)
    assert result.text.startswith("mock:")
    assert stt.calls
