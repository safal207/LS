from __future__ import annotations

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

try:
    import ghostgpt_core  # type: ignore
except Exception as exc:  # pragma: no cover - import availability is environment-dependent
    ghostgpt_core = None
    logger.info("Rust vision core unavailable; Python fallback is active: %s", exc)


class RustSceneChangeAdapter:
    def __init__(self) -> None:
        if ghostgpt_core is None or not hasattr(ghostgpt_core, "RustSceneChangeDetector"):
            raise RuntimeError("RustSceneChangeDetector unavailable")
        self._detector = ghostgpt_core.RustSceneChangeDetector()

    def calculate_scene_score(self, current_frame: np.ndarray, current_ocr_text: str = "") -> float:
        h, w = current_frame.shape[:2]
        frame_rgb = np.ascontiguousarray(current_frame[:, :, :3]).astype(np.uint8)
        return float(
            self._detector.calculate_scene_score(
                frame_rgb.tobytes(),
                int(w),
                int(h),
                current_ocr_text,
            )
        )


class RustPrivacyAdapter:
    def __init__(self) -> None:
        if ghostgpt_core is None or not hasattr(ghostgpt_core, "RustPrivacyRedactor"):
            raise RuntimeError("RustPrivacyRedactor unavailable")
        self._redactor = ghostgpt_core.RustPrivacyRedactor()

    def redact(self, text: str) -> str:
        return str(self._redactor.redact(text))


class RustRhythmAdapter:
    def __init__(self) -> None:
        if ghostgpt_core is None or not hasattr(ghostgpt_core, "RustRhythmAnalyzer"):
            raise RuntimeError("RustRhythmAnalyzer unavailable")
        self._analyzer = ghostgpt_core.RustRhythmAnalyzer()

    def add_score(self, score: float) -> None:
        self._analyzer.add_score(float(score))

    def classify_mode(self) -> str:
        return str(self._analyzer.classify_mode())


class RustFrameBufferAdapter:
    def __init__(self, max_frames: int) -> None:
        if ghostgpt_core is None or not hasattr(ghostgpt_core, "RustFrameBuffer"):
            raise RuntimeError("RustFrameBuffer unavailable")
        self._buffer = ghostgpt_core.RustFrameBuffer(int(max_frames))

    def add_frame(self, frame_data: np.ndarray, metadata: Optional[dict] = None) -> int:
        h, w = frame_data.shape[:2]
        frame_rgb = np.ascontiguousarray(frame_data[:, :, :3]).astype(np.uint8)
        return int(self._buffer.add_frame(frame_rgb.tobytes(), int(w), int(h)))
