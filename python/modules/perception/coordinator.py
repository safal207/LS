from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Any, Optional

from .arl import CognitiveOverlay
from .blackboard import SessionBlackboard
from .bus import CortexIntentBus, PerceptionEventBus
from .cortex import AttentionPolicy, AutoTrigger

logger = logging.getLogger(__name__)


class _FallbackFrameBuffer:
    def __init__(self, max_frames: int = 30) -> None:
        self._frames = deque(maxlen=max_frames)
        self._next_id = 0

    def add_frame(self, frame_data: Any, metadata: Optional[dict] = None) -> int:
        frame_id = self._next_id
        self._next_id += 1
        self._frames.append((frame_id, frame_data, metadata or {}))
        return frame_id


class _FallbackSceneChangeDetector:
    def __init__(self) -> None:
        self._seen_first = False

    def calculate_scene_score(self, current_frame: Any, current_ocr_text: str = "") -> float:
        if not self._seen_first:
            self._seen_first = True
            return 1.0
        return 0.0


class _FallbackRhythmAnalyzer:
    def __init__(self) -> None:
        self._scores: deque[float] = deque(maxlen=10)

    def add_score(self, score: float) -> None:
        self._scores.append(float(score))

    def classify_mode(self) -> str:
        if not self._scores:
            return "Idle"
        avg = sum(self._scores) / len(self._scores)
        if avg > 0.60:
            return "Presentation"
        if avg > 0.20:
            return "Coding"
        return "Discussion"


class VisionSubsystem:
    """The central coordinator for all vision-related perception layers."""

    def __init__(self, monitor_index: int = 1):
        # 1. Core Buses and Blackboard
        self.event_bus = PerceptionEventBus()
        self.intent_bus = CortexIntentBus()
        self.blackboard = SessionBlackboard()

        from .detector import WindowDetector
        from .safety import AuditLog, ConsentManager, PrivacyRedactor

        self.detector = WindowDetector()

        # 2. Defaults that do not require heavy optional deps.
        self.capturer = None
        self.buffer = _FallbackFrameBuffer(max_frames=30)
        self.fusion = _FallbackSceneChangeDetector()
        self.rhythm = _FallbackRhythmAnalyzer()

        # 3. Safety Gate (Layer 16)
        self.privacy = PrivacyRedactor()
        self.consent = ConsentManager()
        self.audit = AuditLog()

        # 4. Upgrade to Python vision implementation if deps are present.
        try:
            from .buffer import FrameBuffer
            from .capturer import ScreenCapturer
            from .fusion import RhythmAnalyzer, SceneChangeDetector

            self.capturer = ScreenCapturer(monitor_index=monitor_index)
            self.buffer = FrameBuffer(max_frames=30)
            self.fusion = SceneChangeDetector()
            self.rhythm = RhythmAnalyzer()
            logger.info("Python vision pipeline enabled.")
        except ModuleNotFoundError as dep_error:
            logger.warning(
                "Python vision deps unavailable, running degraded vision mode: %s",
                dep_error,
            )

        # 5. Optional Rust acceleration with safe fallback.
        try:
            from .rust_accel import (
                RustFrameBufferAdapter,
                RustPrivacyAdapter,
                RustRhythmAdapter,
                RustSceneChangeAdapter,
            )

            self.buffer = RustFrameBufferAdapter(max_frames=30)
            self.privacy = RustPrivacyAdapter()
            self.fusion = RustSceneChangeAdapter()
            self.rhythm = RustRhythmAdapter()
            logger.info("Rust vision acceleration enabled.")
        except Exception as rust_error:
            logger.info("Using non-Rust vision path: %s", rust_error)

        # 6. Proactive Cortex (Layer 13)
        self.policy = AttentionPolicy(max_requests_per_min=5)
        self.auto_trigger = AutoTrigger(threshold=0.5)

        # 7. Augmented Reality Layer (Layer 14)
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
                if self.capturer is None:
                    time.sleep(1.0)
                    continue

                window_context = self.detector.get_active_window()

                if not self.consent.is_capture_allowed(window_context):
                    time.sleep(1.0)
                    continue

                frame_data = self.capturer.capture_frame()
                if frame_data is None:
                    continue

                frame_id = self.buffer.add_frame(frame_data, metadata=window_context)
                self.event_bus.emit(
                    "FrameCaptured", {"frame_id": frame_id, "window": window_context}
                )

                scene_score = self.fusion.calculate_scene_score(
                    frame_data, current_ocr_text=""
                )
                self.rhythm.add_score(scene_score)
                current_activity = self.rhythm.classify_mode()
                self.blackboard.update_mode(current_activity)

                if scene_score > 0.5:
                    self.event_bus.emit(
                        "SceneChange", {"score": scene_score, "frame_id": frame_id}
                    )

                confusion_score = window_context.get("confusion_score", 0.0)
                if self.auto_trigger.should_trigger(scene_score, confusion_score):
                    if self.policy.can_request():
                        model = self.policy.select_model(scene_score, confusion_score)
                        self.intent_bus.emit(
                            "StartObserve", {"model": model, "frame_id": frame_id}
                        )
                        self.audit.log_event(
                            "ObservationTriggered",
                            {"model": model, "frame_id": frame_id},
                        )

                time.sleep(1.0)

            except Exception as e:
                logger.error(f"Error in VisionSubsystem loop: {e}")
                time.sleep(1.0)
