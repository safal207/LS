from __future__ import annotations
import threading
import time
import numpy as np
import pytest
from unittest import mock
from python.modules.perception.coordinator import VisionSubsystem
from python.modules.perception.blackboard import SessionBlackboard
from python.modules.perception.safety import ConsentManager, AuditLog

def test_ocr_redaction_hardening():
    """Verify that sensitive information in OCR text is redacted in the vision subsystem."""
    vision = VisionSubsystem()
    vision._capture_enabled = True

    # Mock capturer to return sensitive text
    vision.capturer = mock.Mock()
    vision.capturer.capture_frame.return_value = np.zeros((16, 16, 3), dtype=np.uint8)
    # Test case including email, password and phone
    sensitive_text = "Email: boss@company.com, Password: secret_pass, Phone: 123-456-7890"
    vision.capturer.extract_ocr_text.return_value = sensitive_text

    # Subscribe to event bus to check emitted data
    emitted_events = []
    vision.event_bus.subscribe(lambda ev: emitted_events.append(ev))

    # Run one loop iteration
    vision._running = True
    with mock.patch("time.sleep"):
        with mock.patch.object(vision, "_is_running", side_effect=[True, False]):
            vision._run_loop()

    # Verify FrameCaptured event payload
    frame_events = [e for e in emitted_events if e.type == "FrameCaptured"]
    assert len(frame_events) > 0
    ocr_result = frame_events[0].payload["ocr"]

    assert "[REDACTED_EMAIL]" in ocr_result
    assert "[REDACTED_PASSWORD]" in ocr_result
    assert "[REDACTED_PHONE]" in ocr_result
    assert "boss@company.com" not in ocr_result
    assert "secret_pass" not in ocr_result
    assert "123-456-7890" not in ocr_result

def test_adaptive_fps_throttling():
    """Verify that the vision subsystem respects the target FPS."""
    vision = VisionSubsystem()
    vision.target_fps = 10.0 # 0.1s interval

    now = 1000.0
    vision._last_capture_time = now - 0.05 # Only 0.05s passed

    sleep_time = vision._calculate_sleep(now)
    # Should sleep for remaining 0.05s
    assert pytest.approx(sleep_time, 0.001) == 0.05

    vision._last_capture_time = now - 0.15 # 0.15s passed
    sleep_time = vision._calculate_sleep(now)
    # Should not sleep
    assert sleep_time == 0

def test_thread_safety_concurrent_access():
    """Verify thread-safety of Blackboard, AuditLog, and ConsentManager under concurrent load."""
    num_threads = 5
    ops_per_thread = 100

    bb = SessionBlackboard()
    audit = AuditLog()
    consent = ConsentManager()

    def worker():
        for i in range(ops_per_thread):
            # Blackboard
            bb.add_fact(f"fact_{i}", 0.8, "test_source")
            # AuditLog
            audit.log_event("test_event", {"i": i})
            # ConsentManager
            consent.is_capture_allowed({"title": "test window"})

    threads = [threading.Thread(target=worker) for _ in range(num_threads)]
    for t in threads: t.start()
    for t in threads: t.join()

    # Verify states
    assert len(bb.get_facts()) == 50 # Max 50
    assert len(audit.get_entries()) == 100 # Max 100
    assert consent.is_capture_allowed({"title": "Safe Window"}) == True
