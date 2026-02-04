from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class CircuitBreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 3
    recovery_timeout_seconds: int = 30
    half_open_success_threshold: int = 2


class CircuitBreaker:
    """
    Smart Circuit Breaker (Phase 4.1)

    All timestamps are stored in UTC.
    NOTE: before_call() has a SIDE EFFECT — it may transition OPEN → HALF_OPEN.
    """

    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config

        self.state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at: Optional[datetime] = None

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    def before_call(self) -> bool:
        """
        Returns True if the call is allowed.
        SIDE EFFECT: If breaker is OPEN and cooldown expired,
        transitions to HALF_OPEN.
        """
        now = datetime.now(timezone.utc)

        if self.state == CircuitBreakerState.OPEN:
            if self._opened_at is None:
                return False

            elapsed = (now - self._opened_at).total_seconds()
            if elapsed >= self.config.recovery_timeout_seconds:
                # Cooldown expired → move to HALF_OPEN
                self.state = CircuitBreakerState.HALF_OPEN
                self._success_count = 0
                self._opened_at = None
                return True

            return False

        return True

    def after_success(self) -> None:
        """
        Called when the protected operation succeeds.
        """
        if self.state == CircuitBreakerState.CLOSED:
            self._failure_count = 0
            return

        if self.state == CircuitBreakerState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.config.half_open_success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self._failure_count = 0
                self._success_count = 0

    def after_failure(self) -> None:
        """
        Called when the protected operation fails.
        """
        now = datetime.now(timezone.utc)

        if self.state == CircuitBreakerState.CLOSED:
            self._failure_count += 1
            if self._failure_count >= self.config.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                self._opened_at = now
            return

        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            self._opened_at = now
            self._success_count = 0
            return

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    def current_state(self) -> CircuitBreakerState:
        return self.state

    def reset(self) -> None:
        """Manual reset."""
        self.state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at = None
