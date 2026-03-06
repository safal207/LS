from __future__ import annotations

import time
import threading
import numpy as np
import pytest
from unittest import mock

from python.modules.perception.coordinator import VisionSubsystem, _FallbackFrameBuffer, _FallbackSceneChangeDetector, _FallbackRhythmAnalyzer, _NoopPrivacyRedactor
from python.modules.perception.buffer import FrameBuffer, Frame
from python.modules.perception.safety import ConsentManager, AuditLog
from python.modules.perception.fusion import RhythmAnalyzer, SceneChangeDetector
from python.modules.perception.capturer import ScreenCapturer
from python.modules.perception.bus import PerceptionEventBus, CortexIntentBus
from python.modules.perception.arl import CognitiveOverlay
from python.modules.perception.blackboard import SessionBlackboard
from python.modules.perception.cortex import AttentionPolicy, AutoTrigger
from python.modules.perception.detector import WindowDetector

def _rust_available() -> bool:
    try:
        from python.modules.perception.rust_accel import RustFrameBufferAdapter
        import ghostgpt_core
        return hasattr(ghostgpt_core, "RustFrameBuffer")
    except (ImportError, RuntimeError):
        return False

def test_frame_to_rgb_buffer_various_inputs():
    from python.modules.perception.rust_accel import _frame_to_rgb_buffer
    # RGBA input
    rgba = np.zeros((10, 10, 4), dtype=np.uint8)
    view, w, h = _frame_to_rgb_buffer(rgba)
    assert w == 10 and h == 10
    assert len(view) == 300 # 10*10*3

    # Non-contiguous input
    non_contig = np.zeros((10, 10, 3), dtype=np.uint8).transpose(1, 0, 2)
    view, w, h = _frame_to_rgb_buffer(non_contig)
    assert w == 10 and h == 10
    assert len(view) == 300

    # astype uint8
    f32 = np.zeros((5, 5, 3), dtype=np.float32)
    view, w, h = _frame_to_rgb_buffer(f32)
    assert len(view) == 75

    # Fallback to bytes
    class FakeFrame:
        def __init__(self):
            self.shape = (2, 2, 3)
        def __iter__(self):
            return iter([0]*12)

    view, w, h = _frame_to_rgb_buffer(FakeFrame())
    assert len(view) == 12

def test_frame_buffer_extra_methods():
    buf = FrameBuffer(max_frames=2)
    id1 = buf.add_frame(np.zeros((4,4,3)))
    id2 = buf.add_frame(np.ones((4,4,3)))

    assert buf.get_frame_by_id(id1) is not None
    assert buf.get_frame_by_id("non-existent") is None

    seq = buf.get_frame_sequence(count=1)
    assert len(seq) == 1
    assert seq[0].id == id2

    buf.clear()
    assert buf.get_latest_frame() is None

@pytest.mark.skipif(not _rust_available(), reason="Rust core not compiled")
def test_rust_adapters():
    from python.modules.perception.rust_accel import RustFrameBufferAdapter, RustRhythmAdapter, RustPrivacyAdapter
    adapter = RustFrameBufferAdapter(max_frames=10)
    frame = np.zeros((16, 16, 3), dtype=np.uint8)
    adapter.add_frame(frame)

    info = adapter.get_latest_frame_metadata()
    assert info is not None
    assert info[1] == 16
    assert info[2] == 16

    rhythm = RustRhythmAdapter()
    rhythm.add_score(0.5)
    assert rhythm.classify_mode() in ["Discussion", "Coding", "Presentation", "Idle"]

    privacy = RustPrivacyAdapter()
    text = "mail test@example.com"
    redacted = privacy.redact(text)
    assert "[REDACTED_EMAIL]" in redacted
    assert "test@example.com" not in redacted

@pytest.mark.skipif(not _rust_available(), reason="Rust core not compiled")
def test_zero_copy_verification():
    from python.modules.perception.rust_accel import _frame_to_rgb_buffer
    # Verify that _frame_to_rgb_buffer returns a memoryview (zero-copy) for contiguous uint8
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    view, w, h = _frame_to_rgb_buffer(frame)
    assert isinstance(view, memoryview)
    view[0] = 255
    assert frame[0, 0, 0] == 255

def test_edge_case_privacy_redaction():
    from python.modules.perception.safety import PrivacyRedactor
    redactor = PrivacyRedactor()

    # Empty string
    assert redactor.redact("") == ""

    # Only PII
    pii = "test@example.com"
    redacted = redactor.redact(pii)
    assert "[REDACTED_EMAIL]" in redacted
    assert "test@example.com" not in redacted

    # Mixed newlines
    mixed = "line1\npassword=secret\r\nline3"
    redacted = redactor.redact(mixed)
    assert "[REDACTED_PASSWORD]" in redacted
    assert "secret" not in redacted

def test_resized_frames_handling():
    vision = VisionSubsystem()
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    # Test all modes
    for mode in ["Discussion", "Coding", "Presentation"]:
        resized = vision._resize_frame_for_mode(frame, mode)
        assert resized.shape[0] in [16, 48, 64]
        assert resized.shape[1] in [16, 48, 64]

def test_concurrent_vision_pipeline_access():
    from python.modules.perception.rust_accel import RustVisionPipeline
    try:
        pipeline = RustVisionPipeline(monitor_index=1)
    except Exception:
        pytest.skip("Rust VisionPipeline unavailable")

    def run_pipeline():
        frame = np.zeros((16, 16, 3), dtype=np.uint8)
        for _ in range(10):
            pipeline.process_frame(frame)

    threads = [threading.Thread(target=run_pipeline) for _ in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    pipeline.stop()

def test_consent_manager_coverage():
    cm = ConsentManager()
    cm.set_global_toggle(False)
    assert not cm.is_capture_allowed({"title": "safe"})

    cm.set_global_toggle(True)
    # Denylist hit
    assert not cm.is_capture_allowed({"title": "password manager"})

    # Allowlist hit
    cm._allowlist = ["chrome"]
    assert cm.is_capture_allowed({"title": "google chrome"})
    assert not cm.is_capture_allowed({"title": "calculator"})

def test_audit_log_coverage():
    log = AuditLog()
    log.max_entries = 2
    log.log_event("type1", {"d": 1})
    log.log_event("type2", {"d": 2})
    log.log_event("type3", {"d": 3})

    entries = log.get_entries()
    assert len(entries) == 2
    assert entries[0]["event_type"] == "type2"

def test_rhythm_analyzer_coverage():
    ra = RhythmAnalyzer()
    assert ra.classify_mode() == "Idle"

    # Presentation
    for _ in range(11): ra.add_score(0.9)
    assert ra.classify_mode() == "Presentation"

    # Coding
    ra._scene_scores = [0.3] * 5
    assert ra.classify_mode() == "Coding"

def test_scene_change_detector_coverage():
    detector = SceneChangeDetector()
    f1 = np.zeros((16, 16, 3), dtype=np.uint8)
    f2 = np.ones((16, 16, 3), dtype=np.uint8) * 255

    detector.calculate_scene_score(f1, "text1")
    # Change OCR text
    score = detector.calculate_scene_score(f2, "text2")
    assert score > 0

    # Different shapes
    f3 = np.zeros((10, 10, 3), dtype=np.uint8)
    score = detector.calculate_scene_score(f3, "text2")
    assert score > 0

def test_vision_subsystem_full_loop_degraded():
    # Force degraded mode by patching capturer availability
    vision = VisionSubsystem()
    vision._capture_enabled = True # Override

    # Mocking necessary parts for the loop
    vision.capturer = mock.Mock()
    vision.capturer.capture_frame.side_effect = [np.zeros((16, 16, 3), dtype=np.uint8), None]
    vision.capturer.extract_ocr_text.return_value = "secret password"

    # Mock policy and trigger
    vision.policy = mock.Mock()
    vision.policy.can_request.return_value = True
    vision.policy.select_model.return_value = "heavy"

    vision.auto_trigger = mock.Mock()
    vision.auto_trigger.should_trigger.return_value = True

    # We need to stop the loop quickly
    def stop_after_a_bit():
        time.sleep(0.5)
        vision.stop()

    threading.Thread(target=stop_after_a_bit).start()
    vision.start()
    # Wait for thread
    deadline = time.time() + 2.0
    while vision._running and time.time() < deadline:
        time.sleep(0.05)

    assert vision.audit.get_entries()

def test_screen_capturer_coverage():
    capturer = ScreenCapturer(monitor_index=0)
    meta = capturer.get_frame_metadata()
    assert meta["status"] in ["mocked", "active", "error"]

    frame = capturer.capture_frame()
    assert frame is not None
    assert frame.shape[2] == 3

def test_capturer_mss_error_handling():
    with mock.patch("mss.mss", side_effect=Exception("mss fail")):
        capturer = ScreenCapturer()
        assert capturer.sct is None
        assert capturer.capture_frame() is not None # fallback to mock

def test_bus_error_handling():
    def exploding_subscriber(ev):
        raise ValueError("boom")

    pbus = PerceptionEventBus()
    pbus.subscribe(exploding_subscriber)
    pbus.emit("test", {}) # Should not raise

    ibus = CortexIntentBus()
    ibus.subscribe(exploding_subscriber)
    ibus.emit("test", {}) # Should not raise

def test_arl_overlay_coverage():
    overlay = CognitiveOverlay()
    for i in range(25):
        overlay.add_hint("Hint", f"c{i}", [])

    assert len(overlay._hints) == 20
    assert overlay.select_best_hint().content == "c24"

    overlay.clear()
    assert overlay.get_active_hints() == []
    assert overlay.select_best_hint() is None

def test_blackboard_coverage():
    bb = SessionBlackboard()
    for i in range(55):
        bb.add_fact(f"fact{i}", 0.9, "f1")

    facts = bb.get_facts()
    assert len(facts) == 50
    assert facts[-1].fact == "fact54"

    bb.set_metadata("k", "v")
    assert bb.get_metadata("k") == "v"

    snap = bb.snapshot()
    assert snap["metadata"]["k"] == "v"
    assert len(snap["facts"]) == 50

def test_cortex_coverage():
    ap = AttentionPolicy(max_requests_per_min=1)
    assert ap.can_request()
    assert not ap.can_request()

    assert ap.select_model(0.9, 0.1) == "9B"
    assert ap.select_model(0.1, 0.9) == "9B"
    assert ap.select_model(0.1, 0.1) == "2B"

    at = AutoTrigger(threshold=0.5)
    assert at.should_trigger(0.8, 0.1)
    assert not at.should_trigger(0.8, 0.1) # cooldown

    at._last_trigger_time = 0
    assert at.should_trigger(0.1, 0.8)
    assert not at.should_trigger(0.1, 0.1)

def test_detector_coverage():
    wd = WindowDetector()
    assert wd.get_active_window()
    assert len(wd.get_all_windows()) == 3

def test_fallbacks_coverage():
    fb = _FallbackFrameBuffer(max_frames=2)
    fb.add_frame("f1")
    fb.add_frame("f2")
    fb.add_frame("f3")
    assert len(fb._frames) == 2

    fsd = _FallbackSceneChangeDetector()
    assert fsd.calculate_scene_score("f1") == 1.0
    assert fsd.calculate_scene_score("f2") == 0.0

    fra = _FallbackRhythmAnalyzer()
    assert fra.classify_mode() == "Idle"
    fra.add_score(0.9)
    assert fra.classify_mode() == "Presentation"
    fra._scores = [0.3]
    assert fra.classify_mode() == "Coding"
    fra._scores = [0.1]
    assert fra.classify_mode() == "Discussion"

    nr = _NoopPrivacyRedactor()
    assert nr.redact("test@example.com") == "[REDACTED_EMAIL]"
    assert nr.redact("") == ""

def test_vision_subsystem_extra_coverage():
    vision = VisionSubsystem()
    # __enter__/__exit__
    with vision as v:
        assert v._running
    assert not vision._running

    # close idempotency
    vision.close()

    # OCR fallback paths
    vision.capturer = mock.Mock()
    del vision.capturer.extract_ocr_text
    assert vision._extract_ocr_text("frame") == ""

    # resize fallback paths
    bad_frame = "not an array"
    assert vision._resize_frame_for_mode(bad_frame, "Coding") is bad_frame

def test_capturer_metadata_error():
    capturer = ScreenCapturer()
    capturer.sct = mock.Mock()
    capturer.sct.monitors = [] # will cause error when accessing monitors[idx]
    meta = capturer.get_frame_metadata()
    assert meta["status"] == "error"

def test_vision_subsystem_no_capturer_loop():
    vision = VisionSubsystem()
    vision.capturer = None
    vision._running = True
    # We want to test the 'if self.capturer is None' branch in _run_loop
    # but we don't want it to run forever.
    # We'll patch time.sleep to raise an exception to break out.
    with mock.patch("time.sleep", side_effect=InterruptedError):
        with pytest.raises(InterruptedError):
            vision._run_loop()
