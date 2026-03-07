from __future__ import annotations

import json
import pathlib
import sys
import time
from dataclasses import asdict, dataclass

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from python.modules.audio.endpoint_detector import SpeechSegment
from python.modules.audio.pipeline import StreamingAudioPipeline
from python.modules.audio.rust_core import RustAudioCore
from python.modules.stt.stt_streaming import MockStreamingSTT


class DummyCapture:
    def __init__(self, chunks: list[np.ndarray]):
        self._chunks = chunks
        self._idx = 0

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def read(self, num_samples: int) -> np.ndarray:
        if self._idx >= len(self._chunks):
            return np.zeros(num_samples, dtype=np.int16)
        chunk = self._chunks[self._idx]
        self._idx += 1
        return chunk


@dataclass
class BenchResult:
    mode: str
    avg_capture_to_stt_ms: float
    p95_capture_to_stt_ms: float
    segments: int


def percentile(data: list[float], q: float) -> float:
    if not data:
        return 0.0
    arr = np.array(data, dtype=np.float64)
    return float(np.percentile(arr, q))


def run_case(use_pyo3: bool) -> BenchResult:
    speech_chunks = [np.full(1024, 6000, dtype=np.int16) for _ in range(8)]
    silence_chunks = [np.zeros(1024, dtype=np.int16) for _ in range(12)]
    chunks = speech_chunks + silence_chunks

    if use_pyo3:
        # Availability check only: StreamingAudioPipeline still uses its own AudioRingBuffer.
        core = RustAudioCore(capacity_samples=16000 * 3)
        if core._impl is None:  # type: ignore[attr-defined]
            raise RuntimeError("PyO3 audio_core extension is not available")

    capture = DummyCapture(chunks)
    events = []

    def event_logger(event: str, **payload):
        events.append((event, payload))

    pipeline = StreamingAudioPipeline(capture, input_rate=16000, target_rate=16000, event_logger=event_logger)
    stt = MockStreamingSTT()
    latencies: list[float] = []

    def on_segment(segment: SpeechSegment) -> None:
        t0 = time.perf_counter()
        stt.transcribe_segment(segment.samples)
        latencies.append((time.perf_counter() - t0) * 1000.0)

    for _ in chunks:
        pipeline.capture_step(1024)
        pipeline.process_available_frames(on_segment)

    flush = pipeline.endpoint.flush(frame_index=9999)
    if flush is not None:
        on_segment(flush)

    return BenchResult(
        mode="with_pyo3" if use_pyo3 else "without_pyo3",
        avg_capture_to_stt_ms=float(np.mean(latencies) if latencies else 0.0),
        p95_capture_to_stt_ms=percentile(latencies, 95),
        segments=len(latencies),
    )


def main() -> None:
    out: list[dict] = []
    out.append(asdict(run_case(use_pyo3=False)))
    try:
        out.append(asdict(run_case(use_pyo3=True)))
    except Exception as exc:
        out.append({"mode": "with_pyo3", "error": str(exc)})
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
