from typing import TYPE_CHECKING

from .breaker import CircuitBreaker, CircuitOpenError
from .cot_adapter import COTAdapter
from .backends import (
    CloudLLMAdapter,
    GonkaLLMAdapter,
    LLMBackend,
    LLMBackendRouter,
    LLMResponse,
    MeritocracyLLMAdapter,
    MimoLLMAdapter,
    LocalLLMAdapter,
    OpenAICompatibleLLMAdapter,
    build_llm_backend,
)
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
    from .routing_operator_api import LLMRoutingOperatorAPI


def __getattr__(name: str):
    if name == "LanguageModel":
        from .llm_module import LanguageModel

        return LanguageModel
    if name == "QwenHandler":
        from .qwen_handler import QwenHandler

        return QwenHandler
    if name == "LLMRoutingOperatorAPI":
        from .routing_operator_api import LLMRoutingOperatorAPI

        return LLMRoutingOperatorAPI
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
    "LLMRoutingOperatorAPI",
    "TemporalContext",
    "LLMBackend",
    "LLMResponse",
    "OpenAICompatibleLLMAdapter",
    "LocalLLMAdapter",
    "CloudLLMAdapter",
    "GonkaLLMAdapter",
    "MimoLLMAdapter",
    "MeritocracyLLMAdapter",
    "LLMBackendRouter",
    "build_llm_backend",
]
