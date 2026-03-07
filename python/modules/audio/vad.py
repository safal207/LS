from __future__ import annotations

from dataclasses import dataclass


try:
    import webrtcvad  # type: ignore
except Exception:
    webrtcvad = None


class WebRTCVAD:
    """WebRTC VAD wrapper with graceful fallback if dependency is absent."""

    def __init__(self, aggressiveness: int = 2, fallback_rms_threshold: float = 700.0) -> None:
        self._fallback_rms_threshold = float(fallback_rms_threshold)
        self._impl = None
        if webrtcvad is not None:
            self._impl = webrtcvad.Vad(max(0, min(3, int(aggressiveness))))

    def is_speech(self, frame_pcm16: bytes, sample_rate: int) -> bool:
        if self._impl is not None:
            return bool(self._impl.is_speech(frame_pcm16, sample_rate))

        # fallback: cheap RMS in PCM16 domain
        if not frame_pcm16:
            return False
        import numpy as np

        pcm = np.frombuffer(frame_pcm16, dtype=np.int16)
        if pcm.size == 0:
            return False
        rms = float((pcm.astype(np.float32) ** 2).mean() ** 0.5)
        return rms >= self._fallback_rms_threshold


@dataclass
class VADDecision:
    frame_index: int
    is_speech: bool


class SileroVAD:
    """Placeholder until real Silero integration. Delegates to WebRTCVAD.

    WebRTCVAD handles its own fallback if webrtcvad package is absent.
    _available stays False until native Silero model is wired up.
    """

    def __init__(self) -> None:
        self._delegate = WebRTCVAD()  # instantiated once, not per-frame
        self._available = False

    def is_speech(self, frame_pcm16: bytes, sample_rate: int) -> bool:
        return self._delegate.is_speech(frame_pcm16, sample_rate)
