from __future__ import annotations

from typing import Literal, Optional

LLMErrorKind = Literal["timeout", "empty_response", "invalid_format", "provider_error"]


class LLMError(Exception):
    def __init__(
        self,
        kind: LLMErrorKind,
        message: str,
        *,
        trip_breaker: bool = True,
        cause: Optional[Exception] = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.trip_breaker = trip_breaker
        self.cause = cause

    def __str__(self) -> str:  # pragma: no cover
        return self.message


class LLMTimeoutError(LLMError):
    def __init__(self, message: str = "LLM request timed out", *, cause: Exception | None = None) -> None:
        super().__init__("timeout", message, trip_breaker=True, cause=cause)


class LLMEmptyResponseError(LLMError):
    def __init__(self, message: str = "LLM returned empty response", *, cause: Exception | None = None) -> None:
        super().__init__("empty_response", message, trip_breaker=False, cause=cause)


class LLMInvalidFormatError(LLMError):
    def __init__(self, message: str = "LLM returned invalid format", *, cause: Exception | None = None) -> None:
        super().__init__("invalid_format", message, trip_breaker=True, cause=cause)


class LLMProviderError(LLMError):
    def __init__(self, message: str = "LLM provider error", *, cause: Exception | None = None) -> None:
        super().__init__("provider_error", message, trip_breaker=True, cause=cause)


def is_timeout_exception(exc: Exception) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    name = exc.__class__.__name__.lower()
    return "timeout" in name


def as_llm_error(exc: Exception) -> LLMError:
    if isinstance(exc, LLMError):
        return exc
    if is_timeout_exception(exc):
        return LLMTimeoutError(cause=exc)
    if isinstance(exc, (KeyError, ValueError, TypeError)):
        return LLMInvalidFormatError(str(exc) or "Invalid response format", cause=exc)
    return LLMProviderError(str(exc) or "Provider error", cause=exc)


def should_trip_breaker(exc: Exception) -> bool:
    return as_llm_error(exc).trip_breaker
