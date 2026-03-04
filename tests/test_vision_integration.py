from __future__ import annotations

import time

import numpy as np

from python.modules.perception.coordinator import VisionSubsystem


def test_full_vision_pipeline_emits_frame_event() -> None:
    vision = VisionSubsystem(monitor_index=1)
    events = []

    class _Detector:
        def get_active_window(self):
            return {"title": "IntegrationTest", "process_name": "pytest"}

    class _Consent:
        def is_capture_allowed(self, _window):
            return True

    class _Capturer:
        def __init__(self):
            self._called = False

        def capture_frame(self):
            if not self._called:
                self._called = True
                return np.zeros((16, 16, 3), dtype=np.uint8)
            vision.stop()
            return None

    vision.pipeline = None
    vision.detector = _Detector()
    vision.consent = _Consent()
    vision.capturer = _Capturer()

    vision.event_bus.subscribe(lambda event: events.append((event.type, event.payload)))

    vision.start()
    deadline = time.time() + 2.0
    while vision._running and time.time() < deadline:
        time.sleep(0.05)

    frame_events = [payload for etype, payload in events if etype == "FrameCaptured"]
    assert frame_events, "expected at least one FrameCaptured event"
    assert "frame_id" in frame_events[0]
    assert frame_events[0]["window"]["title"] == "IntegrationTest"

    vision.close()
