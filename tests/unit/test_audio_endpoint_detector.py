from __future__ import annotations

import numpy as np

from python.modules.audio.endpoint_detector import EndpointDetector


def test_endpoint_emits_after_600ms_silence() -> None:
    detector = EndpointDetector(frame_ms=20, silence_ms_to_endpoint=600, min_speech_ms=60)

    frame = np.ones(320, dtype=np.int16)
    frame_index = 0

    # 10 speech frames
    for _ in range(10):
        seg = detector.process_frame(frame, True, frame_index)
        assert seg is None
        frame_index += 1

    emitted = None
    # 30 silence frames => 600ms endpoint
    for _ in range(30):
        emitted = detector.process_frame(np.zeros(320, dtype=np.int16), False, frame_index)
        frame_index += 1

    assert emitted is not None
    assert emitted.samples.size >= 320 * 10
