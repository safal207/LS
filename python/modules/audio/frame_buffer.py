from __future__ import annotations

import numpy as np


class AudioRingBuffer:
    """Single-process low-overhead ring buffer for PCM16 audio.

    Design notes:
    - Pre-allocated contiguous numpy storage.
    - O(1) push/pop index arithmetic.
    - No disk I/O, minimal copying.

    Concurrency model is optimized for single-producer/single-consumer usage.
    """

    def __init__(self, capacity_samples: int = 16000 * 10) -> None:
        if capacity_samples <= 0:
            raise ValueError("capacity_samples must be > 0")
        self._buf = np.zeros(capacity_samples, dtype=np.int16)
        self._cap = capacity_samples
        self._read = 0
        self._write = 0
        self._size = 0

    def available_samples(self) -> int:
        return self._size

    def free_samples(self) -> int:
        return self._cap - self._size

    def push(self, samples: np.ndarray) -> int:
        if samples.dtype != np.int16:
            samples = samples.astype(np.int16, copy=False)
        if samples.ndim != 1:
            samples = samples.reshape(-1)

        n = int(samples.size)
        if n <= 0:
            return 0

        # keep latest data under pressure
        if n > self._cap:
            samples = samples[-self._cap :]
            n = self._cap

        overflow = max(0, n - self.free_samples())
        if overflow:
            self._read = (self._read + overflow) % self._cap
            self._size -= overflow

        first = min(n, self._cap - self._write)
        self._buf[self._write : self._write + first] = samples[:first]
        second = n - first
        if second:
            self._buf[:second] = samples[first:]

        self._write = (self._write + n) % self._cap
        self._size += n
        return n

    def pop(self, max_samples: int) -> np.ndarray:
        n = min(max(0, int(max_samples)), self._size)
        if n == 0:
            return np.empty(0, dtype=np.int16)

        out = np.empty(n, dtype=np.int16)
        first = min(n, self._cap - self._read)
        out[:first] = self._buf[self._read : self._read + first]
        second = n - first
        if second:
            out[first:] = self._buf[:second]

        self._read = (self._read + n) % self._cap
        self._size -= n
        return out

    def peek(self, max_samples: int) -> np.ndarray:
        n = min(max(0, int(max_samples)), self._size)
        if n == 0:
            return np.empty(0, dtype=np.int16)

        out = np.empty(n, dtype=np.int16)
        first = min(n, self._cap - self._read)
        out[:first] = self._buf[self._read : self._read + first]
        second = n - first
        if second:
            out[first:] = self._buf[:second]
        return out
