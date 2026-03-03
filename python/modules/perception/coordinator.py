from __future__ import annotations
import logging
import threading
import time
from typing import Optional

from .bus import PerceptionEventBus, CortexIntentBus
from .blackboard import SessionBlackboard
from .capturer import ScreenCapturer
from .detector import WindowDetector
from .buffer import FrameBuffer
from .safety import PrivacyRedactor, ConsentManager, AuditLog
from .fusion import SceneChangeDetector, RhythmAnalyzer
from .cortex import AttentionPolicy, AutoTrigger
from .arl import CognitiveOverlay

logger = logging.getLogger(__name__)

class VisionSubsystem:
    """The central coordinator for all vision-related perception layers."""
    def __init__(self, monitor_index: int = 1):
        # 1. Core Buses and Blackboard
        self.event_bus = PerceptionEventBus()
        self.intent_bus = CortexIntentBus()
        self.blackboard = SessionBlackboard()

        # 2. Perception Layer
        self.capturer = ScreenCapturer(monitor_index=monitor_index)
        self.detector = WindowDetector()
        self.buffer = FrameBuffer(max_frames=30)

        # 3. Safety Gate (Layer 16)
        self.privacy = PrivacyRedactor()
        self.consent = ConsentManager()
        self.audit = AuditLog()

        # 4. Temporal Fusion (Layer 15)
        self.fusion = SceneChangeDetector()
        self.rhythm = RhythmAnalyzer()

        # 5. Proactive Cortex (Layer 13)
        self.policy = AttentionPolicy(max_requests_per_min=5)
        self.auto_trigger = AutoTrigger(threshold=0.5)

        # 6. Augmented Reality Layer (Layer 14)
        self.arl = CognitiveOverlay()

        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Starts the vision subsystem loop."""
        if self._running:
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
