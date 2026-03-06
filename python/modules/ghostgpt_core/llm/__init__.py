from typing import TYPE_CHECKING

from .breaker import CircuitBreaker, CircuitOpenError
from .cot_adapter import COTAdapter
from .errors import (
    LLMEmptyResponseError,
    LLMError,
    LLMInvalidFormatError,
    LLMProviderError,
    LLMTimeoutError,
)
from .temporal import TemporalContext

if TYPE_CHECKING:
    from .llm_module import LanguageModel
    from .qwen_handler import QwenHandler


def __getattr__(name: str):
    if name == "LanguageModel":
        from .llm_module import LanguageModel

        return LanguageModel
    if name == "QwenHandler":
        from .qwen_handler import QwenHandler

        return QwenHandler
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "CircuitBreaker",
    "CircuitOpenError",
    "COTAdapter",
    "LLMError",
    "LLMTimeoutError",
    "LLMEmptyResponseError",
    "LLMInvalidFormatError",
    "LLMProviderError",
    "LanguageModel",
    "QwenHandler",
    "TemporalContext",
]
