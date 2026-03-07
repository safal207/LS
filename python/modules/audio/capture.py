from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from .interfaces import IAudioCapture

logger = logging.getLogger(__name__)

try:
    import pyaudio
except Exception:
    pyaudio = None


class PortAudioCapture(IAudioCapture):
    def __init__(self, sample_rate: int = 16000, channels: int = 1, device_index: Optional[int] = None):
        self.sample_rate = sample_rate
        self.channels = channels
        self.device_index = device_index
        self._pa = None
        self._stream = None

    def start(self) -> None:
        if pyaudio is None:
            raise RuntimeError("PyAudio is unavailable")
        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            input_device_index=self.device_index,
            frames_per_buffer=1024,
        )

    def stop(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop_stream()
                self._stream.close()
            finally:
                self._stream = None
        if self._pa is not None:
            self._pa.terminate()
            self._pa = None

    def read(self, num_samples: int) -> np.ndarray:
        if self._stream is None:
            raise RuntimeError("capture is not started")
        data = self._stream.read(num_samples, exception_on_overflow=False)
        return np.frombuffer(data, dtype=np.int16)


class WASAPICapture(PortAudioCapture):
    """Windows-ready capture facade.

    Uses PortAudio backend; intended to be wired to WASAPI loopback host API
    through deployment-specific device selection.
    """

    def __init__(self, sample_rate: int = 16000, channels: int = 1, device_index: Optional[int] = None):
        super().__init__(sample_rate=sample_rate, channels=channels, device_index=device_index)
