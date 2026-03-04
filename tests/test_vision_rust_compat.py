from __future__ import annotations

import pytest

np = pytest.importorskip("numpy")

from python.modules.perception.fusion import SceneChangeDetector
from python.modules.perception.safety import PrivacyRedactor


def _rust_available() -> bool:
    try:
        import ghostgpt_core  # type: ignore

        return hasattr(ghostgpt_core, "RustSceneChangeDetector")
    except ImportError:
        return False


def test_python_scene_detector_first_frame_high_score() -> None:
    detector = SceneChangeDetector()
    frame = np.zeros((64, 64, 3), dtype=np.uint8)
    score = detector.calculate_scene_score(frame, "")
    assert score > 0.9


def test_python_scene_detector_identical_frame_low_score() -> None:
    detector = SceneChangeDetector()
    frame = np.zeros((64, 64, 3), dtype=np.uint8)
    detector.calculate_scene_score(frame, "")
    score = detector.calculate_scene_score(frame, "")
    assert score < 0.05


def test_python_scene_detector_changed_frame_higher_score() -> None:
    detector = SceneChangeDetector()
    frame1 = np.zeros((64, 64, 3), dtype=np.uint8)
    frame2 = np.ones((64, 64, 3), dtype=np.uint8) * 255
    detector.calculate_scene_score(frame1, "")
    score = detector.calculate_scene_score(frame2, "")
    assert score > 0.2


def test_privacy_redactor_contract() -> None:
    redactor = PrivacyRedactor()
    text = "mail test@example.com phone 123-456-7890 password: qwerty"
    redacted = redactor.redact(text)

    assert "[REDACTED_EMAIL]" in redacted or "test@example.com" not in redacted
    assert "[REDACTED_PHONE]" in redacted or "123-456-7890" not in redacted
    assert "[REDACTED_PASSWORD]" in redacted or "qwerty" not in redacted


def test_privacy_redactor_preserves_safe_text() -> None:
    redactor = PrivacyRedactor()
    safe = "The meeting is at 3pm in room 42."
    assert redactor.redact(safe) == safe


@pytest.mark.skipif(not _rust_available(), reason="Rust ghostgpt_core not compiled")
def test_rust_python_scene_score_compatibility() -> None:
    from python.modules.perception.rust_accel import RustSceneChangeAdapter

    py_detector = SceneChangeDetector()
    rs_detector = RustSceneChangeAdapter()

    frame = np.zeros((64, 64, 3), dtype=np.uint8)

    py_first = py_detector.calculate_scene_score(frame, "")
    rs_first = rs_detector.calculate_scene_score(frame, "")
    assert abs(py_first - rs_first) < 0.2
