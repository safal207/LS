from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional


class CircuitOpenError(Exception):
    pass


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    cooldown_seconds: int = 10
    _failure_count: int = 0
    _opened_at: Optional[float] = None

    def _now(self) -> float:
        return time.time()

    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if (self._now() - self._opened_at) >= self.cooldown_seconds:
            self.reset()
            return False
        return True

    def before_call(self) -> None:
        if self.is_open():
            raise CircuitOpenError("Circuit breaker is open")

    def after_success(self) -> None:
        self.reset()

    def after_failure(self, exc: Exception) -> None:
        self._failure_count += 1
        if self._failure_count >= self.failure_threshold:
            if self._opened_at is None:
                self._opened_at = self._now()

    def reset(self) -> None:
        self._failure_count = 0
        self._opened_at = None
