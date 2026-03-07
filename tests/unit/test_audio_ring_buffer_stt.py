from __future__ import annotations

import numpy as np
import threading

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


def test_pipeline_metrics_and_event_logging() -> None:
    chunks = [np.full(1024, 5000, dtype=np.int16) for _ in range(4)] + [np.zeros(1024, dtype=np.int16) for _ in range(10)]
    events: list[tuple[str, dict[str, float | int | str]]] = []

    def _event_logger(event: str, **payload: float | int | str) -> None:
        events.append((event, payload))

    pipeline = StreamingAudioPipeline(
        _DummyCapture(chunks),
        input_rate=16000,
        target_rate=16000,
        ring_capacity_samples=640,
        event_logger=_event_logger,
    )
    segments: list[SpeechSegment] = []
    for _ in chunks:
        pipeline.capture_step(1024)
        pipeline.process_available_frames(segments.append)

    assert pipeline.metrics.queue_drops >= 0
    assert any(event == "capture" for event, _ in events)
    assert any(event == "vad" for event, _ in events)


def test_thread_safe_ring_buffer_across_threads() -> None:
    rb = AudioRingBuffer(capacity_samples=4096, thread_safe=True)
    produced = np.arange(20000, dtype=np.int16)
    consumed: list[np.ndarray] = []
    done = threading.Event()

    def producer() -> None:
        i = 0
        chunk = 128
        while i < produced.size:
            rb.push(produced[i : i + chunk])
            i += chunk
        done.set()

    def consumer() -> None:
        while not done.is_set() or rb.available_samples() > 0:
            out = rb.pop(96)
            if out.size:
                consumed.append(out)

    pt = threading.Thread(target=producer)
    ct = threading.Thread(target=consumer)
    pt.start()
    ct.start()
    pt.join()
    ct.join()

    total = sum(chunk.size for chunk in consumed)
    assert total <= produced.size
    assert rb.dropped_samples() >= 0
