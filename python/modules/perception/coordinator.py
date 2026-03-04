from __future__ import annotations

import logging
import threading
import time
from collections import deque
from importlib import import_module
from typing import Any, Optional

from .arl import CognitiveOverlay
from .blackboard import SessionBlackboard
from .bus import CortexIntentBus, PerceptionEventBus
from .cortex import AttentionPolicy, AutoTrigger
from .detector import WindowDetector
from .safety import AuditLog, ConsentManager

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


class _NoopPrivacyRedactor:
    def redact(self, text: str) -> str:
        return text


class VisionSubsystem:
    """The central coordinator for all vision-related perception layers."""

    def __init__(self, monitor_index: int = 1):
        self.event_bus = PerceptionEventBus()
        self.intent_bus = CortexIntentBus()
        self.blackboard = SessionBlackboard()

        self.detector = WindowDetector()

        self.capturer = None
        self.pipeline = None
        self.buffer = _FallbackFrameBuffer(max_frames=30)
        self.fusion = _FallbackSceneChangeDetector()
        self.rhythm = _FallbackRhythmAnalyzer()

        self.privacy = _NoopPrivacyRedactor()
        self.consent = ConsentManager()
        self.audit = AuditLog()

        self.policy = AttentionPolicy(max_requests_per_min=5)
        self.auto_trigger = AutoTrigger(threshold=0.5)
        self.arl = CognitiveOverlay()

        self._running = False
        self._capture_enabled = True
        self._thread: Optional[threading.Thread] = None
        self._last_degraded_log_ts = 0.0

        self._fallback_to_python_components(monitor_index)
        self._try_enable_rust_acceleration(monitor_index)

    def _try_enable_rust_acceleration(self, monitor_index: int) -> None:
        try:
            from .rust_accel import (
                RustFrameBufferAdapter,
                RustPrivacyAdapter,
                RustRhythmAdapter,
                RustSceneChangeAdapter,
                RustVisionPipeline,
            )

            self.pipeline = RustVisionPipeline(monitor_index=monitor_index)
            self.buffer = RustFrameBufferAdapter(max_frames=30)
            self.privacy = RustPrivacyAdapter()
            self.fusion = RustSceneChangeAdapter()
            self.rhythm = RustRhythmAdapter()
            if self.capturer is None:
                logger.warning(
                    "Rust pipeline disabled: no capturer available. Falling back to Python path."
                )
                self.pipeline.stop()
                self.pipeline = None
        except Exception as rust_error:
            logger.warning("Rust vision unavailable, falling back to Python: %s", rust_error)
            self.pipeline = None

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

    def close(self):
        """Explicitly release subsystem resources."""
        self.stop()
        if self.pipeline is not None:
            try:
                self.pipeline.stop()
            except Exception:
                pass
            self.pipeline = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

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

    def _run_loop(self):
        """Main vision processing cycle."""
        while self._running:
            try:
                if self.capturer is None:
                    now = time.time()
                    if now - self._last_degraded_log_ts >= 60.0:
                        logger.warning(
                            "Vision subsystem remains in degraded mode (capturer unavailable)."
                        )
                        self._last_degraded_log_ts = now
                    time.sleep(1.0)
                    continue

                window_context = self.detector.get_active_window()

                if not self.consent.is_capture_allowed(window_context):
                    time.sleep(1.0)
                    continue

                ocr_text = ""
                redacted_ocr = (
                    self.privacy.redact(ocr_text)
                    if hasattr(self.privacy, "redact")
                    else ocr_text
                )
                frame_id = None

                frame_data = self.capturer.capture_frame()
                if frame_data is None:
                    continue

                frame_id = self.buffer.add_frame(frame_data, metadata=window_context)
                self.event_bus.emit(
                    "FrameCaptured", {"frame_id": frame_id, "window": window_context}
                )

                if self.pipeline is not None:
                    scene_score, current_activity, _, _ = self.pipeline.process_frame(
                        frame_data,
                        current_ocr_text=redacted_ocr,
                        mode=self.blackboard.current_mode,
                    )
                else:
                    scene_score = self.fusion.calculate_scene_score(
                        frame_data, current_ocr_text=redacted_ocr
                    )
                    self.rhythm.add_score(scene_score)
                    current_activity = self.rhythm.classify_mode()
                self.blackboard.update_mode(current_activity)

                if scene_score > 0.5:
                    payload = {"score": scene_score}
                    if frame_id is not None:
                        payload["frame_id"] = frame_id
                    self.event_bus.emit("SceneChange", payload)

                confusion_score = window_context.get("confusion_score", 0.0)
                if self.auto_trigger.should_trigger(scene_score, confusion_score):
                    if self.policy.can_request():
                        model = self.policy.select_model(scene_score, confusion_score)
                        payload = {"model": model}
                        if frame_id is not None:
                            payload["frame_id"] = frame_id
                        self.intent_bus.emit("StartObserve", payload)
                        self.audit.log_event("ObservationTriggered", payload)

                time.sleep(1.0)

            except Exception as e:
                logger.error(f"Error in VisionSubsystem loop: {e}")
                time.sleep(1.0)
