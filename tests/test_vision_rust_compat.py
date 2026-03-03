from __future__ import annotations

import pytest

np = pytest.importorskip("numpy")

from python.modules.perception.fusion import SceneChangeDetector
from python.modules.perception.safety import PrivacyRedactor


def test_python_scene_detector_contract_identical_frame():
    detector = SceneChangeDetector()
    frame = np.zeros((64, 64, 3), dtype=np.uint8)

    assert detector.calculate_scene_score(frame, "") == 1.0
    assert detector.calculate_scene_score(frame, "") == 0.0


def test_privacy_redactor_contract():
    redactor = PrivacyRedactor()
    text = "mail test@example.com phone 123-456-7890 password: qwerty"
    redacted = redactor.redact(text)

    assert "[REDACTED_EMAIL]" in redacted
    assert "[REDACTED_PHONE]" in redacted
    assert "[REDACTED_PASSWORD]" in redacted
