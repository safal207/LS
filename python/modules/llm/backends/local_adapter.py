from __future__ import annotations

import logging
from time import perf_counter
from typing import Any, Optional

from ..errors import LLMEmptyResponseError
from ..qwen_handler import QwenHandler
from .base import LLMResponse, normalize_messages

logger = logging.getLogger(__name__)


class LocalLLMAdapter:
    provider = "local"

    def __init__(
        self,
        handler: Optional[QwenHandler] = None,
        *,
        model: str = "",
        fallback_model: str = "",
    ) -> None:
        self._handler = handler or QwenHandler(
            use_cloud_api=False,
            model_name=model or None,
            raise_on_error=True,
        )
        self.model = model or self._handler.model_name
        self.fallback_model = fallback_model or self.model

    @property
    def handler(self) -> QwenHandler:
        return self._handler

    @handler.setter
    def handler(self, value) -> None:
        self._handler = value
        self.model = getattr(value, "model_name", self.model)

    def generate(
        self,
        messages,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        metadata: Optional[dict[str, Any]] = None,
        *,
        stream: bool = False,
        on_token=None,
    ) -> LLMResponse:
        _ = temperature, max_tokens, timeout, metadata
        prompt_messages = normalize_messages(messages, system_prompt=system_prompt)
        prompt = prompt_messages[-1]["content"] if prompt_messages else ""
        start = perf_counter()
        current_model = getattr(self._handler, "model_name", self.model)
        tried_fallback = False
        error: Optional[str] = None
        text = ""

        try:
            text = self._handler.generate_response(
                prompt,
                messages=prompt_messages or None,
                stream=stream,
                on_token=on_token,
            )
            if not isinstance(text, str) or not text.strip():
                raise LLMEmptyResponseError("Local LLM returned empty response")
            latency_ms = (perf_counter() - start) * 1000
            logger.info(
                "llm provider=%s model=%s latency_ms=%.1f success=true",
                self.provider,
                current_model,
                latency_ms,
            )
            self.model = current_model
            return LLMResponse(
                text=text.strip(),
                model=current_model,
                provider=self.provider,
                latency_ms=latency_ms,
            )
        except Exception as exc:
            error = str(exc)
            if (
                self.fallback_model
                and self.fallback_model != current_model
                and hasattr(self._handler, "model_name")
            ):
                tried_fallback = True
                try:
                    self._handler.model_name = self.fallback_model
                    text = self._handler.generate_response(
                        prompt,
                        messages=prompt_messages or None,
                        stream=stream,
                        on_token=on_token,
                    )
                    if not isinstance(text, str) or not text.strip():
                        raise LLMEmptyResponseError("Local fallback returned empty response")
                    latency_ms = (perf_counter() - start) * 1000
                    logger.info(
                        "llm provider=%s model=%s latency_ms=%.1f success=true fallback_from=%s",
                        self.provider,
                        self.fallback_model,
                        latency_ms,
                        current_model,
                    )
                    self.model = self.fallback_model
                    return LLMResponse(
                        text=text.strip(),
                        model=self.fallback_model,
                        provider=self.provider,
                        latency_ms=latency_ms,
                        was_fallback_used=True,
                        fallback_from=current_model,
                        fallback_to=self.fallback_model,
                    )
                except Exception as fallback_exc:
                    error = str(fallback_exc)
                finally:
                    if hasattr(self._handler, "model_name"):
                        self._handler.model_name = current_model

            latency_ms = (perf_counter() - start) * 1000
            logger.warning(
                "llm provider=%s model=%s latency_ms=%.1f success=false error=%s",
                self.provider,
                current_model,
                latency_ms,
                error,
            )
            return LLMResponse(
                text="",
                model=self.fallback_model if tried_fallback else current_model,
                provider=self.provider,
                latency_ms=latency_ms,
                error=error,
                was_fallback_used=tried_fallback,
                fallback_from=current_model if tried_fallback else None,
                fallback_to=self.fallback_model if tried_fallback else None,
            )

