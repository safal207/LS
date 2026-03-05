from __future__ import annotations

import threading

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


def test_python_scene_detector_shifted_pattern_detects_change() -> None:
    detector = SceneChangeDetector()
    base = np.zeros((64, 64, 3), dtype=np.uint8)
    base[:, 24:40, :] = 255
    shifted = np.roll(base, shift=6, axis=1)

    detector.calculate_scene_score(base, "")
    score = detector.calculate_scene_score(shifted, "")
    assert score > 0.05

def test_privacy_redactor_contract() -> None:
    redactor = PrivacyRedactor()
    text = "mail test@example.com phone 123-456-7890 password: qwerty"
    redacted = redactor.redact(text)

    assert "[REDACTED_EMAIL]" in redacted, "email not redacted"
    assert "test@example.com" not in redacted, "raw email leaked"
    assert "[REDACTED_PHONE]" in redacted, "phone not redacted"
    assert "123-456-7890" not in redacted, "raw phone leaked"
    assert "[REDACTED_PASSWORD]" in redacted, "password not redacted"
    assert "qwerty" not in redacted, "raw password value leaked"

def test_privacy_redactor_preserves_safe_text() -> None:
    redactor = PrivacyRedactor()
    safe = "The meeting is at 3pm in room 42."
    assert redactor.redact(safe) == safe

@pytest.mark.skipif(not _rust_available(), reason="Rust ghostgpt_core not compiled")
def test_rust_python_scene_score_compatibility() -> None:
    from python.modules.perception.rust_accel import RustSceneChangeAdapter

    py_detector = SceneChangeDetector()
    rs_detector = RustSceneChangeAdapter()

    frame1 = np.zeros((64, 64, 3), dtype=np.uint8)
    frame2 = np.ones((64, 64, 3), dtype=np.uint8) * 128
    frame3 = np.ones((64, 64, 3), dtype=np.uint8) * 255

    paired_scores = []
    for frame in (frame1, frame2, frame3):
        py_score = py_detector.calculate_scene_score(frame, "")
        rs_score = rs_detector.calculate_scene_score(frame, "")
        paired_scores.append((py_score, rs_score, int(frame.mean())))

    for py_score, rs_score, mean in paired_scores:
        assert abs(py_score - rs_score) < 0.10, (
            f"Python={py_score:.3f} vs Rust={rs_score:.3f} diverged on frame "
            f"mean={mean}"
        )

def test_rust_api_surface_contract() -> None:
    if not _rust_available():
        pytest.skip("Rust ghostgpt_core not compiled")

    import ghostgpt_core  # type: ignore

    expected_classes = [
        "RustSceneChangeDetector",
        "RustPrivacyRedactor",
        "RustFrameBuffer",
        "RustRhythmAnalyzer",
        "VisionPipeline",
    ]
    for class_name in expected_classes:
        assert hasattr(ghostgpt_core, class_name), f"Missing Rust class: {class_name}"

    detector = ghostgpt_core.RustSceneChangeDetector()
    assert hasattr(detector, "calculate_scene_score")

    redactor = ghostgpt_core.RustPrivacyRedactor()
    assert hasattr(redactor, "redact")

    buffer = ghostgpt_core.RustFrameBuffer(4)
    assert hasattr(buffer, "add_frame")
    assert hasattr(buffer, "latest_frame")
    assert hasattr(buffer, "latest_frame_info")
    assert hasattr(buffer, "is_empty")

    frame_id = buffer.add_frame(bytes([0] * (64 * 64 * 3)), 64, 64)
    frame_info = buffer.latest_frame_info()
    assert frame_info is not None
    assert frame_info[0] == frame_id
    assert frame_info[1:] == (64, 64)

    rhythm = ghostgpt_core.RustRhythmAnalyzer()
    assert hasattr(rhythm, "add_score")
    assert hasattr(rhythm, "classify_mode")

    pipeline = ghostgpt_core.VisionPipeline(1)
    assert hasattr(pipeline, "start")
    assert hasattr(pipeline, "stop")
    assert hasattr(pipeline, "process_frame")


@pytest.mark.skipif(not _rust_available(), reason="Rust ghostgpt_core not compiled")
def test_rust_python_scene_score_sequence_compatibility() -> None:
    from python.modules.perception.rust_accel import RustSceneChangeAdapter

    py_detector = SceneChangeDetector()
    rs_detector = RustSceneChangeAdapter()

    sequence = [
        np.zeros((64, 64, 3), dtype=np.uint8),
        np.ones((64, 64, 3), dtype=np.uint8) * 32,
        np.ones((64, 64, 3), dtype=np.uint8) * 64,
        np.ones((64, 64, 3), dtype=np.uint8) * 96,
    ]

    py_scores = [py_detector.calculate_scene_score(frame, "") for frame in sequence]
    rs_scores = [rs_detector.calculate_scene_score(frame, "") for frame in sequence]

    for idx, (py_score, rs_score) in enumerate(zip(py_scores, rs_scores)):
        assert abs(py_score - rs_score) < 0.10, (
            f"Frame #{idx}: Python={py_score:.3f} vs Rust={rs_score:.3f}"
        )

    # Both implementations should react to a gradual change sequence
    # with non-flat deltas beyond the initial warm-up frame.
    assert max(py_scores[1:]) > min(py_scores[1:])
    assert max(rs_scores[1:]) > min(rs_scores[1:])


@pytest.mark.skipif(not _rust_available(), reason="Rust ghostgpt_core not compiled")
def test_rust_python_scene_score_shifted_pattern_compatibility() -> None:
    from python.modules.perception.rust_accel import RustSceneChangeAdapter

    py_detector = SceneChangeDetector()
    rs_detector = RustSceneChangeAdapter()

    frame1 = np.zeros((64, 64, 3), dtype=np.uint8)
    frame1[:, 24:40, :] = 255
    frame2 = np.roll(frame1, shift=6, axis=1)

    py_detector.calculate_scene_score(frame1, "")
    rs_detector.calculate_scene_score(frame1, "")

    py_score = py_detector.calculate_scene_score(frame2, "")
    rs_score = rs_detector.calculate_scene_score(frame2, "")

    assert py_score > 0.05
    assert rs_score > 0.05
    assert abs(py_score - rs_score) < 0.10


@pytest.mark.skipif(not _rust_available(), reason="Rust ghostgpt_core not compiled")
def test_rust_frame_buffer_concurrent_access() -> None:
    import ghostgpt_core  # type: ignore

    buffer = ghostgpt_core.RustFrameBuffer(100)

    def writer(seed: int) -> None:
        for i in range(300):
            value = (seed + i) % 255
            frame = np.full((64, 64, 3), value, dtype=np.uint8)
            buffer.add_frame(frame.tobytes(), 64, 64)

    def reader() -> None:
        for _ in range(400):
            _ = buffer.latest_frame_info()

    threads = [
        threading.Thread(target=writer, args=(0,)),
        threading.Thread(target=writer, args=(17,)),
        threading.Thread(target=reader),
    ]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert buffer.len() <= 100


@pytest.mark.skipif(not _rust_available(), reason="Rust ghostgpt_core not compiled")
def test_vision_pipeline_concurrent_access() -> None:
    import ghostgpt_core  # type: ignore

    pipeline = ghostgpt_core.VisionPipeline(1)
    pipeline.start()

    errors: list[Exception] = []

    def worker(seed: int) -> None:
        try:
            for i in range(40):
                value = (seed + i) % 255
                frame = np.full((64, 64, 3), value, dtype=np.uint8)
                pipeline.process_frame(frame.tobytes(), 64, 64, "", None)
        except Exception as exc:  # pragma: no cover - defensive in threaded code
            errors.append(exc)

    threads = [
        threading.Thread(target=worker, args=(1,)),
        threading.Thread(target=worker, args=(99,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    pipeline.stop()
    assert not errors


@pytest.mark.skipif(not _rust_available(), reason="Rust ghostgpt_core not compiled")
def test_rust_python_scene_score_real_like_resized_parity() -> None:
    from python.modules.perception.rust_accel import RustSceneChangeAdapter

    py_detector = SceneChangeDetector()
    rs_detector = RustSceneChangeAdapter()

    rng = np.random.default_rng(7)
    frame1 = rng.integers(0, 255, size=(240, 320, 3), dtype=np.uint8)
    frame2 = np.roll(frame1, shift=8, axis=1)

    import cv2

    f1 = cv2.resize(frame1, (16, 16), interpolation=cv2.INTER_NEAREST)
    f2 = cv2.resize(frame2, (16, 16), interpolation=cv2.INTER_NEAREST)

    py_detector.calculate_scene_score(f1, "")
    rs_detector.calculate_scene_score(f1, "")

    py_score = py_detector.calculate_scene_score(f2, "")
    rs_score = rs_detector.calculate_scene_score(f2, "")

    assert abs(py_score - rs_score) < 0.15


@pytest.mark.skipif(not _rust_available(), reason="Rust ghostgpt_core not compiled")
def test_rust_python_scene_score_real_like_resized_parity_with_ocr() -> None:
    from python.modules.perception.rust_accel import RustSceneChangeAdapter

    py_detector = SceneChangeDetector()
    rs_detector = RustSceneChangeAdapter()

    rng = np.random.default_rng(17)
    frame1 = rng.integers(0, 255, size=(240, 320, 3), dtype=np.uint8)
    frame2 = np.roll(frame1, shift=5, axis=0)

    import cv2

    f1 = cv2.resize(frame1, (48, 48), interpolation=cv2.INTER_NEAREST)
    f2 = cv2.resize(frame2, (48, 48), interpolation=cv2.INTER_NEAREST)

    py_detector.calculate_scene_score(f1, "status idle")
    rs_detector.calculate_scene_score(f1, "status idle")

    py_score = py_detector.calculate_scene_score(f2, "status busy")
    rs_score = rs_detector.calculate_scene_score(f2, "status busy")

    assert abs(py_score - rs_score) < 0.20
