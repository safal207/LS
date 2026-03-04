from __future__ import annotations

import logging
from collections import deque
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import ghostgpt_core  # type: ignore
except Exception as exc:  # pragma: no cover - import availability is environment-dependent
    ghostgpt_core = None
    logger.info("Rust vision core unavailable; Python fallback is active: %s", exc)


def _frame_to_rgb_buffer(frame: Any) -> Tuple[Any, int, int]:
    """Convert ndarray-like frame to an RGB-compatible bytes-like object.

    Prefers buffer views over eager `tobytes()` to reduce intermediate copies.
    """
    shape = getattr(frame, "shape", None)
    if not shape or len(shape) < 2:
        raise ValueError("frame must expose shape (H, W, C)")

    height = int(shape[0])
    width = int(shape[1])

    if len(shape) >= 3 and int(shape[2]) > 3 and hasattr(frame, "__getitem__"):
        frame = frame[:, :, :3]

    if hasattr(frame, "astype"):
        frame = frame.astype("uint8", copy=False)

    try:
        view = memoryview(frame)
        if view.ndim > 1:
            view = view.cast("B")
        return view, width, height
    except TypeError:
        pass

    if hasattr(frame, "tobytes"):
        return frame.tobytes(), width, height

    return bytes(frame), width, height


class RustVisionPipeline:
    """Pipeline + Adaptive Resolution wrapper around Rust core."""

    def __init__(self, monitor_index: int = 1):
        if ghostgpt_core is None or not hasattr(ghostgpt_core, "VisionPipeline"):
            raise RuntimeError("Rust VisionPipeline unavailable")

        self._core = ghostgpt_core.VisionPipeline(int(monitor_index))
        self._core.start()

    def stop(self) -> None:
        self._core.stop()

    def process_frame(
        self,
        frame_data: Any,
        current_ocr_text: str = "",
        mode: Optional[str] = None,
    ) -> Tuple[float, str, int, int]:
        frame_rgb, w, h = _frame_to_rgb_buffer(frame_data)
        score, activity, target_w, target_h = self._core.process_frame(
            frame_rgb,
            int(w),
            int(h),
            current_ocr_text,
            mode,
        )
        return float(score), str(activity), int(target_w), int(target_h)


class RustSceneChangeAdapter:
    def __init__(self) -> None:
        if ghostgpt_core is None or not hasattr(ghostgpt_core, "RustSceneChangeDetector"):
            raise RuntimeError("RustSceneChangeDetector unavailable")
        self._detector = ghostgpt_core.RustSceneChangeDetector()

    def calculate_scene_score(self, current_frame: Any, current_ocr_text: str = "") -> float:
        frame_rgb, w, h = _frame_to_rgb_buffer(current_frame)
        return float(
            self._detector.calculate_scene_score(
                frame_rgb,
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
        self._max_frames = int(max_frames)
        self._metadata_by_id: dict[int, Optional[dict]] = {}
        self._metadata_order: deque[int] = deque(maxlen=max_frames)

    def add_frame(self, frame_data: Any, metadata: Optional[dict] = None) -> int:
        frame_rgb, w, h = _frame_to_rgb_buffer(frame_data)
        frame_id = int(self._buffer.add_frame(frame_rgb, int(w), int(h)))

        if len(self._metadata_order) == self._max_frames:
            evicted_id = self._metadata_order[0]
            self._metadata_by_id.pop(evicted_id, None)

        self._metadata_order.append(frame_id)
        self._metadata_by_id[frame_id] = metadata
        return frame_id

    def get_metadata(self, frame_id: int) -> Optional[dict]:
        return self._metadata_by_id.get(frame_id)
