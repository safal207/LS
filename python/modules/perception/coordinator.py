from __future__ import annotations
import logging
import threading
import time
from importlib import import_module
from typing import Any, Optional

from .bus import PerceptionEventBus, CortexIntentBus
from .blackboard import SessionBlackboard
from .detector import WindowDetector
from .safety import ConsentManager, AuditLog
from .cortex import AttentionPolicy, AutoTrigger
from .arl import CognitiveOverlay

logger = logging.getLogger(__name__)


class _FallbackFrameBuffer:
    def __init__(self, max_frames: int = 30):
        self.max_frames = max_frames

    def add_frame(self, *_args: Any, **_kwargs: Any) -> str:
        return "fallback_frame_0"


class _FallbackSceneChangeDetector:
    def calculate_scene_score(self, *_args: Any, **_kwargs: Any) -> float:
        return 0.0


class _FallbackRhythmAnalyzer:
    def add_score(self, _score: float) -> None:
        return

    def classify_mode(self) -> str:
        return "Idle"


class _NoopPrivacyRedactor:
    def redact(self, text: str) -> str:
        return text

class VisionSubsystem:
    """The central coordinator for all vision-related perception layers."""
    def __init__(self, monitor_index: int = 1):
        # 1. Core Buses and Blackboard
        self.event_bus = PerceptionEventBus()
        self.intent_bus = CortexIntentBus()
        self.blackboard = SessionBlackboard()

        # 2. Perception Layer
        self.detector = WindowDetector()
        self.capturer = None
        self.buffer = None

        # 3. Safety Gate (Layer 16)
        self.privacy = _NoopPrivacyRedactor()
        self.consent = ConsentManager()
        self.audit = AuditLog()

        # 4. Temporal Fusion (Layer 15)
        self.fusion = _FallbackSceneChangeDetector()
        self.rhythm = _FallbackRhythmAnalyzer()

        # 5. Proactive Cortex (Layer 13)
        self.policy = AttentionPolicy(max_requests_per_min=5)
        self.auto_trigger = AutoTrigger(threshold=0.5)

        # 6. Augmented Reality Layer (Layer 14)
        self.arl = CognitiveOverlay()

        self._running = False
        self._capture_enabled = True
        self._thread: Optional[threading.Thread] = None
        self._fallback_to_python_components(monitor_index)

    def start(self):
        """Starts the vision subsystem loop."""
        if self._running:
            return
        if not self._capture_enabled:
            logger.warning("VisionSubsystem cannot start: capture stack is unavailable.")
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("VisionSubsystem started.")

    def stop(self):
        """Stops the vision subsystem loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("VisionSubsystem stopped.")

    def _run_loop(self):
        """Main vision processing cycle."""
        while self._running:
            try:
                if self.capturer is None:
                    logger.error("VisionSubsystem capturer unavailable, stopping processing loop.")
                    self._running = False
                    self._capture_enabled = False
                    break

                # Cycle start
                # 1. Capture screen context
                window_context = self.detector.get_active_window()

                # 2. Consent Gate (Layer 16)
                if not self.consent.is_capture_allowed(window_context):
                    time.sleep(1.0) # Check again soon
                    continue

                # 3. Perception: Raw Capture
                frame_data = self.capturer.capture_frame()
                if frame_data is None:
                    continue

                frame_id = self.buffer.add_frame(frame_data, metadata=window_context)
                self.event_bus.emit("FrameCaptured", {"frame_id": frame_id, "window": window_context})

                # 4. Temporal Fusion (Layer 15)
                # In v0.1: Scene score calculation without full OCR integration
                scene_score = self.fusion.calculate_scene_score(frame_data, current_ocr_text="")
                self.rhythm.add_score(scene_score)
                current_activity = self.rhythm.classify_mode()
                self.blackboard.update_mode(current_activity)

                if scene_score > 0.5:
                    self.event_bus.emit("SceneChange", {"score": scene_score, "frame_id": frame_id})

                # 5. Proactive Cortex (Layer 13)
                # Simple confusion score from simulated context
                confusion_score = window_context.get("confusion_score", 0.0)
                if self.auto_trigger.should_trigger(scene_score, confusion_score):
                     if self.policy.can_request():
                         model = self.policy.select_model(scene_score, confusion_score)
                         self.intent_bus.emit("StartObserve", {"model": model, "frame_id": frame_id})
                         self.audit.log_event("ObservationTriggered", {"model": model, "frame_id": frame_id})

                time.sleep(1.0) # Limit capture to 1 FPS for efficiency

            except Exception as e:
                logger.error(f"Error in VisionSubsystem loop: {e}")
                time.sleep(1.0)

    def _fallback_to_python_components(self, monitor_index: int) -> None:
        """Initialize Python vision components if available, otherwise disable capture."""
        self.capturer = None
        self.buffer = _FallbackFrameBuffer(max_frames=30)
        self.fusion = _FallbackSceneChangeDetector()
        self.rhythm = _FallbackRhythmAnalyzer()
        self.privacy = _NoopPrivacyRedactor()

        try:
            capturer_module = import_module("python.modules.perception.capturer")
            buffer_module = import_module("python.modules.perception.buffer")
            fusion_module = import_module("python.modules.perception.fusion")
            safety_module = import_module("python.modules.perception.safety")

            self.capturer = capturer_module.ScreenCapturer(monitor_index=monitor_index)
            self.buffer = buffer_module.FrameBuffer(max_frames=30)
            self.fusion = fusion_module.SceneChangeDetector()
            self.rhythm = fusion_module.RhythmAnalyzer()
            self.privacy = safety_module.PrivacyRedactor()
            self._capture_enabled = True
            logger.info("VisionSubsystem initialized Python perception components.")
        except (ModuleNotFoundError, AttributeError) as dep_error:
            logger.error(
                "Python perception components unavailable: %s. Vision capture disabled.", dep_error
            )
            self._capture_enabled = False
            self._running = False
