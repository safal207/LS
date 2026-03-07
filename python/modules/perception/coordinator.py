from __future__ import annotations

import logging
import re
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
    _EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
    _PHONE_RE = re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")
    _PASSWORD_RE = re.compile(r"(?i)(password|passwd|secret)[:= ]+[^\s]+")

    def __init__(self) -> None:
        self._warned = False

    def redact(self, text: str) -> str:
        if not text:
            return text
        if not self._warned:
            logger.warning(
                "Noop privacy redactor active in degraded mode; applying minimal built-in masking."
            )
            self._warned = True

        redacted = self._EMAIL_RE.sub("[REDACTED_EMAIL]", text)
        redacted = self._PHONE_RE.sub("[REDACTED_PHONE]", redacted)
        redacted = self._PASSWORD_RE.sub(r"\1: [REDACTED_PASSWORD]", redacted)
        return redacted


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

        self.privacy_redactor = _NoopPrivacyRedactor()
        self.consent = ConsentManager()
        self.audit = AuditLog()

        self.policy = AttentionPolicy(max_requests_per_min=5)
        self.auto_trigger = AutoTrigger(threshold=0.5)
        self.arl = CognitiveOverlay()

        self._state_lock = threading.Lock()
        self._monitor_index = int(monitor_index)
        self._running = False
        self._capture_enabled = True
        self.target_fps = 2.0
        self._last_capture_time = 0.0
        self._thread: Optional[threading.Thread] = None
        self._last_degraded_log_ts = 0.0
        self._ocr_unavailable_warned = False

        self._fallback_to_python_components(self._monitor_index)
        self._try_enable_rust_acceleration(self._monitor_index)

    def _is_running(self) -> bool:
        with self._state_lock:
            return self._running

    def _set_degraded_components(self) -> None:
        self.pipeline = None
        self.capturer = None
        self.buffer = _FallbackFrameBuffer(max_frames=30)
        self.fusion = _FallbackSceneChangeDetector()
        self.rhythm = _FallbackRhythmAnalyzer()
        self.privacy_redactor = _NoopPrivacyRedactor()

    def _try_enable_rust_acceleration(self, monitor_index: int) -> None:
        try:
            from .rust_accel import (
                RustFrameBufferAdapter,
                RustPrivacyAdapter,
                RustRhythmAdapter,
                RustSceneChangeAdapter,
                RustVisionPipeline,
            )

            rust_pipeline = RustVisionPipeline(monitor_index=monitor_index)
            rust_buffer = RustFrameBufferAdapter(max_frames=30)
            rust_privacy = RustPrivacyAdapter()
            rust_fusion = RustSceneChangeAdapter()
            rust_rhythm = RustRhythmAdapter()

            if self.capturer is None:
                logger.warning(
                    "Rust pipeline disabled: no capturer available. Falling back to degraded components."
                )
                rust_pipeline.stop()
                self._set_degraded_components()
                self._capture_enabled = False
                return

            self.pipeline = rust_pipeline
            self.buffer = rust_buffer
            self.privacy_redactor = rust_privacy
            self.fusion = rust_fusion
            self.rhythm = rust_rhythm
        except Exception as rust_error:
            logger.warning("Rust vision unavailable, falling back to Python: %s", rust_error)
            self.pipeline = None

    def start(self):
        """Starts the vision subsystem loop."""
        with self._state_lock:
            if self._running:
                return

            if not self._capture_enabled:
                self._fallback_to_python_components(self._monitor_index)
                if self._capture_enabled and self.pipeline is None:
                    self._try_enable_rust_acceleration(self._monitor_index)

            if not self._capture_enabled:
                logger.warning("VisionSubsystem cannot start: capture stack is unavailable.")
                return

            self._running = True
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            thread = self._thread

        thread.start()
        logger.info("VisionSubsystem started.")

    def stop(self):
        """Stops the vision subsystem loop."""
        with self._state_lock:
            if not self._running:
                logger.debug("VisionSubsystem already stopped.")
                return
            self._running = False
            thread = self._thread
            self._thread = None

        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
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

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def _fallback_to_python_components(self, monitor_index: int) -> None:
        """Initialize Python vision components if available, otherwise disable capture."""
        self._set_degraded_components()

        try:
            capturer_module = import_module("python.modules.perception.capturer")
            buffer_module = import_module("python.modules.perception.buffer")
            fusion_module = import_module("python.modules.perception.fusion")
            safety_module = import_module("python.modules.perception.safety")

            self.capturer = capturer_module.ScreenCapturer(monitor_index=monitor_index)
            self.buffer = buffer_module.FrameBuffer(max_frames=30)
            self.fusion = fusion_module.SceneChangeDetector()
            self.rhythm = fusion_module.RhythmAnalyzer()
            self.privacy_redactor = safety_module.PrivacyRedactor()
            self._capture_enabled = True
            logger.info("VisionSubsystem initialized Python perception components.")
        except (ModuleNotFoundError, AttributeError) as dep_error:
            logger.warning(
                "Python perception components unavailable: %s. Will retry on next start().",
                dep_error,
            )
            self._capture_enabled = False

    def _extract_ocr_text(self, frame_data: Any) -> str:
        if self.capturer is None:
            return ""

        if not hasattr(self.capturer, "extract_ocr_text"):
            if not self._ocr_unavailable_warned:
                logger.info(
                    "Capturer has no extract_ocr_text(); OCR delta disabled for current backend."
                )
                self._ocr_unavailable_warned = True
            return ""

        try:
            ocr_text = self.capturer.extract_ocr_text(frame_data)
            return str(ocr_text or "")
        except Exception as ocr_error:
            logger.debug("OCR extraction failed: %s", ocr_error)
            return ""

    def _resize_frame_for_mode(self, frame_data: Any, mode: str) -> Any:
        target_by_mode = {
            "Presentation": (64, 64),
            "Coding": (48, 48),
        }
        target_w, target_h = target_by_mode.get(mode, (16, 16))

        shape = getattr(frame_data, "shape", None)
        if not shape or len(shape) < 2:
            return frame_data

        frame_h, frame_w = int(shape[0]), int(shape[1])
        if frame_h == target_h and frame_w == target_w:
            return frame_data

        try:
            import cv2

            return cv2.resize(frame_data, (target_w, target_h), interpolation=cv2.INTER_NEAREST)
        except Exception:
            try:
                import numpy as np

                y_idx = np.linspace(0, frame_h - 1, target_h).astype(int)
                x_idx = np.linspace(0, frame_w - 1, target_w).astype(int)
                return frame_data[np.ix_(y_idx, x_idx)]
            except Exception:
                logger.warning(
                    "Adaptive resize unavailable (cv2/numpy path failed); using original frame dimensions."
                )
                return frame_data

    def _calculate_sleep(self, now: float) -> float:
        """Calculates the time to sleep to maintain target FPS."""
        elapsed = now - self._last_capture_time
        return max(0, (1.0 / self.target_fps) - elapsed)

    def _safe_capture(self) -> Any:
        try:
            frame_data = self.capturer.capture_frame()
            self._last_capture_time = time.time()
            return frame_data
        except Exception as e:
            logger.error(f"Frame capture failed: {e}")
            return None

    def _run_loop(self):
        """Main vision processing cycle with crash protection."""
        while self._is_running():
            try:
                now = time.time()
                if self.capturer is None:
                    if now - self._last_degraded_log_ts >= 60.0:
                        logger.warning(
                            "Vision subsystem remains in degraded mode (capturer unavailable)."
                        )
                        self._last_degraded_log_ts = now
                    time.sleep(1.0)
                    continue

                sleep_time = self._calculate_sleep(now)
                if sleep_time > 0:
                    time.sleep(sleep_time)

                window_context = self.detector.get_active_window()

                if not self.consent.is_capture_allowed(window_context):
                    time.sleep(1.0)
                    continue

                frame_data = self._safe_capture()
                if frame_data is None:
                    continue

                raw_ocr = self._extract_ocr_text(frame_data)
                safe_ocr = (
                    self.privacy_redactor.redact(raw_ocr)
                    if hasattr(self.privacy_redactor, "redact")
                    else raw_ocr
                )
                frame_id = self.buffer.add_frame(frame_data, metadata=window_context)
                self.event_bus.emit(
                    "FrameCaptured",
                    {"frame_id": frame_id, "window": window_context, "ocr": safe_ocr},
                )

                if self.pipeline is not None:
                    scene_score, current_activity, _, _ = self.pipeline.process_frame(
                        frame_data,
                        current_ocr_text=safe_ocr,
                        mode=self.blackboard.current_mode,
                    )
                else:
                    resized_frame = self._resize_frame_for_mode(
                        frame_data, self.blackboard.current_mode
                    )
                    scene_score = self.fusion.calculate_scene_score(
                        resized_frame, current_ocr_text=safe_ocr
                    )
                    self.rhythm.add_score(scene_score)
                    current_activity = self.rhythm.classify_mode()

                self.blackboard.update_mode(current_activity)

                if scene_score > 0.5:
                    self.event_bus.emit(
                        "SceneChange",
                        {"score": scene_score, "frame_id": frame_id},
                    )

                confusion_score = window_context.get("confusion_score", 0.0)
                if self.auto_trigger.should_trigger(scene_score, confusion_score):
                    if self.policy.can_request():
                        model = self.policy.select_model(scene_score, confusion_score)
                        payload = {"model": model, "frame_id": frame_id}
                        self.intent_bus.emit("StartObserve", payload)
                        self.audit.log_event("ObservationTriggered", payload)

            except Exception as e:
                logger.error(f"Error in VisionSubsystem loop: {e}")
                time.sleep(1.0)
