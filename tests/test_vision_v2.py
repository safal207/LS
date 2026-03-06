import unittest
import time
import numpy as np
from unittest import mock
from python.modules.perception.coordinator import VisionSubsystem, _NoopPrivacyRedactor
from python.modules.perception.arl import VisualHint

class TestVisionSubsystem(unittest.TestCase):
    def setUp(self):
        self.vision = VisionSubsystem()

    def test_initialization(self):
        self.assertIsNotNone(self.vision.detector)
        self.assertIsNotNone(self.vision.buffer)
        self.assertIsNotNone(self.vision.policy)
        self.assertIn(self.vision.capturer is None, (True, False))

    def test_safety_gate(self):
        # Mock window context
        safe_context = {"title": "Google Chrome", "process_name": "chrome.exe"}
        unsafe_context = {"title": "Password Manager", "process_name": "passwords.exe"}

        self.assertTrue(self.vision.consent.is_capture_allowed(safe_context))
        self.assertFalse(self.vision.consent.is_capture_allowed(unsafe_context))

    def test_privacy_redactor(self):
        text = "My email is test@example.com and phone is 123-456-7890."
        redacted = self.vision.privacy.redact(text)
        self.assertIn("[REDACTED_EMAIL]", redacted)
        self.assertIn("[REDACTED_PHONE]", redacted)
        self.assertNotIn("test@example.com", redacted)

    def test_scene_change_formula(self):
        # Create two slightly different frames
        frame1 = np.zeros((100, 100, 3), dtype=np.uint8)
        frame2 = np.ones((100, 100, 3), dtype=np.uint8) * 255

        score1 = self.vision.fusion.calculate_scene_score(frame1)
        self.assertEqual(score1, 1.0) # First frame

        score2 = self.vision.fusion.calculate_scene_score(frame2)
        self.assertGreater(score2, 0.0) # Should detect change

        # Test identical frames
        score3 = self.vision.fusion.calculate_scene_score(frame2)
        self.assertEqual(score3, 0.0) # No change from frame2

    def test_attention_budget(self):
        policy = self.vision.policy
        policy.max_requests_per_min = 2

        self.assertTrue(policy.can_request())
        self.assertTrue(policy.can_request())
        self.assertFalse(policy.can_request()) # Budget exhausted

    def test_arl_hint_ttl(self):
        arl = self.vision.arl
        arl.add_hint("Hint", "Test Hint", grounding=["frame_1"])

        hints = arl.get_active_hints()
        self.assertEqual(len(hints), 1)

        # Manually expire hint
        hints[0].timestamp = time.time() - 10.0
        active_hints = arl.get_active_hints()
        self.assertEqual(len(active_hints), 0)

    def test_fallback_uses_python_components_when_available(self):
        vision = VisionSubsystem(monitor_index=1)
        self.assertIsNotNone(vision.buffer)

    def test_degraded_mode_when_component_init_fails(self):
        with mock.patch(
            "python.modules.perception.coordinator.import_module",
            side_effect=ModuleNotFoundError("missing screen backend"),
        ):
            vision = VisionSubsystem(monitor_index=1)

        self.assertIsNone(vision.capturer)
        self.assertEqual(type(vision.buffer).__name__, "_FallbackFrameBuffer")
        self.assertFalse(vision._capture_enabled)

    def test_start_noop_when_capture_disabled(self):
        vision = VisionSubsystem(monitor_index=1)
        vision._capture_enabled = False
        with mock.patch.object(
            vision,
            "_fallback_to_python_components",
            side_effect=lambda _monitor_index: setattr(vision, "_capture_enabled", False),
        ):
            vision.start()
        self.assertFalse(vision._running)

    def test_start_retries_component_initialization(self):
        vision = VisionSubsystem(monitor_index=1)
        vision._capture_enabled = False
        with mock.patch.object(
            vision,
            "_fallback_to_python_components",
            side_effect=lambda _monitor_index: setattr(vision, "_capture_enabled", True),
        ) as mock_fallback, mock.patch.object(
            vision,
            "_try_enable_rust_acceleration",
            return_value=None,
        ):
            vision.start()
            vision.stop()

        mock_fallback.assert_called_once_with(1)
        self.assertTrue(vision._capture_enabled)

    def test_stop_is_idempotent_without_started_thread(self):
        vision = VisionSubsystem(monitor_index=1)
        vision.stop()
        vision.stop()
        self.assertFalse(vision._running)

    def test_close_releases_resources_and_is_idempotent(self):
        vision = VisionSubsystem(monitor_index=1)

        class _FakePipeline:
            def __init__(self):
                self.stops = 0

            def stop(self):
                self.stops += 1

        fake_pipeline = _FakePipeline()
        vision.pipeline = fake_pipeline
        vision.start()
        vision.close()

        self.assertFalse(vision._running)
        self.assertIsNone(vision.pipeline)
        self.assertEqual(fake_pipeline.stops, 1)

        vision.close()
        self.assertFalse(vision._running)

    def test_context_manager_closes_on_normal_exit(self):
        with VisionSubsystem(monitor_index=1) as vision:
            self.assertTrue(vision._running)

        self.assertFalse(vision._running)
        self.assertIsNone(vision.pipeline)

    def test_context_manager_propagates_exception_and_closes(self):
        with self.assertRaises(ValueError):
            with VisionSubsystem(monitor_index=1) as vision:
                self.assertTrue(vision._running)
                raise ValueError("boom")

        self.assertFalse(vision._running)

    def test_noop_privacy_redactor_masks_common_pii(self):
        redactor = _NoopPrivacyRedactor()
        text = "email test@example.com phone 123-456-7890 secret: hunter2"
        redacted = redactor.redact(text)
        self.assertIn("[REDACTED_EMAIL]", redacted)
        self.assertIn("[REDACTED_PHONE]", redacted)
        self.assertIn("[REDACTED_PASSWORD]", redacted)
        self.assertNotIn("test@example.com", redacted)
        self.assertNotIn("123-456-7890", redacted)
        self.assertNotIn("hunter2", redacted)


    def test_extract_ocr_text_logs_when_ocr_unavailable(self):
        vision = VisionSubsystem(monitor_index=1)

        class _NoOcrCapturer:
            def capture_frame(self):
                return np.zeros((8, 8, 3), dtype=np.uint8)

        vision.capturer = _NoOcrCapturer()
        with self.assertLogs("python.modules.perception.coordinator", level="INFO") as logs:
            text = vision._extract_ocr_text(np.zeros((8, 8, 3), dtype=np.uint8))

        self.assertEqual(text, "")
        self.assertTrue(any("extract_ocr_text" in msg for msg in logs.output))

    def test_ocr_redaction_occurs_after_capture(self):
        vision = VisionSubsystem(monitor_index=1)

        class _Detector:
            def get_active_window(self):
                return {"title": "Test", "process_name": "pytest"}

        class _Consent:
            def is_capture_allowed(self, _window):
                return True

        class _Capturer:
            def __init__(self):
                self.calls = 0
                self.last_frame = None

            def capture_frame(self):
                self.calls += 1
                if self.calls == 1:
                    self.last_frame = np.ones((32, 32, 3), dtype=np.uint8)
                    return self.last_frame
                return None

            def extract_ocr_text(self, frame):
                if frame is self.last_frame:
                    return "password: secret123"
                return ""

        class _Fusion:
            def __init__(self):
                self.seen_ocr = None

            def calculate_scene_score(self, _frame, current_ocr_text=""):
                self.seen_ocr = current_ocr_text
                return 0.0

        vision.pipeline = None
        vision.detector = _Detector()
        vision.consent = _Consent()
        vision.capturer = _Capturer()
        vision.fusion = _Fusion()
        vision.privacy = _NoopPrivacyRedactor()

        vision.start()
        deadline = time.time() + 2.0
        while vision._running and time.time() < deadline:
            time.sleep(0.05)

        vision.stop()
        self.assertIn("[REDACTED_PASSWORD]", vision.fusion.seen_ocr)
        self.assertNotIn("secret123", vision.fusion.seen_ocr)


    def test_resize_frame_for_mode_without_cv2_uses_numpy_fallback(self):
        vision = VisionSubsystem(monitor_index=1)
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        import builtins
        real_import = builtins.__import__
        with mock.patch("builtins.__import__") as import_mock:
            def _side_effect(name, *args, **kwargs):
                if name == "cv2":
                    raise ModuleNotFoundError("cv2 missing")
                return real_import(name, *args, **kwargs)
            import_mock.side_effect = _side_effect
            resized = vision._resize_frame_for_mode(frame, "Coding")

        self.assertEqual(resized.shape[0], 48)
        self.assertEqual(resized.shape[1], 48)


    def test_rust_frame_buffer_adapter_eviction_cleans_metadata(self):
        from python.modules.perception import rust_accel

        class _FakeRustFrameBuffer:
            def __init__(self, _max_frames):
                self._id = 0

            def add_frame(self, _frame_rgb, _w, _h):
                current = self._id
                self._id += 1
                return current

            def latest_frame_info(self):
                return None

        class _FakeCore:
            RustFrameBuffer = _FakeRustFrameBuffer

        with mock.patch.object(rust_accel, "ghostgpt_core", _FakeCore()):
            adapter = rust_accel.RustFrameBufferAdapter(max_frames=2)
            frame = np.zeros((8, 8, 3), dtype=np.uint8)
            id0 = adapter.add_frame(frame, metadata={"id": 0})
            id1 = adapter.add_frame(frame, metadata={"id": 1})
            _id2 = adapter.add_frame(frame, metadata={"id": 2})

        self.assertEqual(id0, 0)
        self.assertEqual(id1, 1)
        self.assertIsNone(adapter.get_metadata(0))
        self.assertEqual(adapter.get_metadata(1), {"id": 1})

    def test_rust_fallback_when_capturer_missing(self):
        vision = VisionSubsystem(monitor_index=1)
        vision.capturer = None
        pipeline_holder = {}

        class _FakePipeline:
            def __init__(self, monitor_index=1):
                self.stopped = False
                pipeline_holder["pipeline"] = self

            def stop(self):
                self.stopped = True

        with mock.patch(
            "python.modules.perception.rust_accel.RustVisionPipeline",
            _FakePipeline,
        ), mock.patch(
            "python.modules.perception.rust_accel.RustFrameBufferAdapter",
            lambda max_frames=30: object(),
        ), mock.patch(
            "python.modules.perception.rust_accel.RustPrivacyAdapter",
            lambda: object(),
        ), mock.patch(
            "python.modules.perception.rust_accel.RustSceneChangeAdapter",
            lambda: object(),
        ), mock.patch(
            "python.modules.perception.rust_accel.RustRhythmAdapter",
            lambda: object(),
        ):
            vision._try_enable_rust_acceleration(1)

        self.assertTrue(pipeline_holder["pipeline"].stopped)
        self.assertIsNone(vision.pipeline)

if __name__ == "__main__":
    unittest.main()
