from __future__ import annotations

import numpy as np

from python.modules.audio.vad import WebRTCVAD


def test_vad_fallback_detects_voice_like_signal() -> None:
    vad = WebRTCVAD(fallback_rms_threshold=400.0)
    # 20 ms @ 16kHz
    t = np.arange(320)
    sig = (1200 * np.sin(2 * np.pi * 220 * t / 16000)).astype(np.int16)

    assert vad.is_speech(sig.tobytes(), 16000)


def test_vad_fallback_rejects_silence() -> None:
    vad = WebRTCVAD(fallback_rms_threshold=400.0)
    silence = np.zeros(320, dtype=np.int16)

    assert not vad.is_speech(silence.tobytes(), 16000)
