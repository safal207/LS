from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Protocol

import numpy as np


class IAudioCapture(ABC):
    """Audio capture backend interface.

    Expected output format:
    - PCM16
    - mono
    - configurable sample rate (default 16k)
    """

    @abstractmethod
    def start(self) -> None:
        """Start capturing audio."""

    @abstractmethod
    def stop(self) -> None:
        """Stop capturing audio."""

    @abstractmethod
    def read(self, num_samples: int) -> np.ndarray:
        """Return PCM16 samples as 1D numpy array."""


class IRingBuffer(Protocol):
    def push(self, samples: np.ndarray) -> int:
        ...

    def pop(self, max_samples: int) -> np.ndarray:
        ...

    def available_samples(self) -> int:
        ...


class IResampler(Protocol):
    def resample(self, samples: np.ndarray, in_rate: int, out_rate: int) -> np.ndarray:
        ...


class IVAD(ABC):
    """Voice activity detector over 20ms frames."""

    @abstractmethod
    def is_speech(self, frame_pcm16: bytes, sample_rate: int) -> bool:
        ...


class IFrameSource(Protocol):
    def read_frames(self) -> Iterable[np.ndarray]:
        ...
