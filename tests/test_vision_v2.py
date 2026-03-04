import unittest
import time
import numpy as np
from unittest import mock
from python.modules.perception.coordinator import VisionSubsystem
from python.modules.perception.arl import VisualHint

class TestVisionSubsystem(unittest.TestCase):
    def setUp(self):
        self.vision = VisionSubsystem()

    def test_initialization(self):
        self.assertIsNotNone(self.vision.capturer)
        self.assertIsNotNone(self.vision.detector)
        self.assertIsNotNone(self.vision.buffer)
        self.assertIsNotNone(self.vision.policy)

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
        self.assertIsNotNone(vision.capturer)
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
        with mock.patch(
            "python.modules.perception.coordinator.import_module",
            side_effect=ModuleNotFoundError("missing screen backend"),
        ):
            vision = VisionSubsystem(monitor_index=1)

        self.assertFalse(vision._capture_enabled)

        class _FakeCapturer:
            def capture_frame(self):
                return None

        class _FakeBuffer:
            def __init__(self, max_frames=30):
                self.max_frames = max_frames
            def add_frame(self, _frame, metadata=None):
                return 0

        class _FakeFusion:
            def calculate_scene_score(self, _frame, current_ocr_text=""):
                return 0.0

        class _FakeRhythm:
            def add_score(self, _score):
                return
            def classify_mode(self):
                return "Idle"

        class _FakePrivacy:
            def redact(self, text):
                return text

        fake_modules = {
            "python.modules.perception.capturer": type("M", (), {"ScreenCapturer": lambda *args, **kwargs: _FakeCapturer()}),
            "python.modules.perception.buffer": type("M", (), {"FrameBuffer": _FakeBuffer}),
            "python.modules.perception.fusion": type("M", (), {"SceneChangeDetector": _FakeFusion, "RhythmAnalyzer": _FakeRhythm}),
            "python.modules.perception.safety": type("M", (), {"PrivacyRedactor": _FakePrivacy}),
        }

        with mock.patch(
            "python.modules.perception.coordinator.import_module",
            side_effect=lambda name: fake_modules[name],
        ), mock.patch.object(vision, "_try_enable_rust_acceleration", return_value=None):
            vision.start()
            vision.stop()

        self.assertTrue(vision._capture_enabled)

    def test_stop_is_idempotent_without_started_thread(self):
        vision = VisionSubsystem(monitor_index=1)
        vision.stop()
        vision.stop()
        self.assertFalse(vision._running)

if __name__ == "__main__":
    unittest.main()
