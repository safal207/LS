from __future__ import annotations

import logging
import re
from time import perf_counter
from typing import Any, Optional

from .base import LLMResponse, normalize_messages

logger = logging.getLogger(__name__)

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>\s*", re.IGNORECASE | re.DOTALL)


def _sanitize_model_text(text: str) -> str:
    if not text:
        return ""
    return _THINK_BLOCK_RE.sub("", text).strip()


class OpenAICompatibleLLMAdapter:
    def __init__(
        self,
        *,
        provider: str,
        model: str,
        base_url: str,
        api_key: str,
        timeout_sec: float = 120.0,
        enabled: bool = True,
    ) -> None:
        self.provider = provider
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.timeout_sec = timeout_sec
        self.enabled = enabled
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except Exception as exc:
            raise RuntimeError(f"openai dependency unavailable: {exc}") from exc
        self._client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=float(self.timeout_sec),
        )
        return self._client

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
        _ = metadata
        start = perf_counter()
        if not self.enabled:
            return LLMResponse(
                text="",
                model=self.model,
                provider=self.provider,
                latency_ms=0.0,
                error=f"{self.provider} backend disabled",
            )
        if not self.api_key or not self.base_url or not self.model:
            return LLMResponse(
                text="",
                model=self.model,
                provider=self.provider,
                latency_ms=0.0,
                error=f"{self.provider} backend not configured",
            )

        prompt_messages = normalize_messages(messages, system_prompt=system_prompt)
        try:
            client = self._get_client()
            if stream:
                completion = client.chat.completions.create(
                    model=self.model,
                    messages=prompt_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout or self.timeout_sec,
                    stream=True,
                )
                parts: list[str] = []
                for chunk in completion:
                    delta = getattr(chunk.choices[0].delta, "content", None)
                    if not delta:
                        continue
                    parts.append(delta)
                    if on_token is not None:
                        on_token(delta)
                text = _sanitize_model_text("".join(parts))
                raw = None
            else:
                completion = client.chat.completions.create(
                    model=self.model,
                    messages=prompt_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout or self.timeout_sec,
                )
                text = _sanitize_model_text(completion.choices[0].message.content or "")
                raw = completion.model_dump() if hasattr(completion, "model_dump") else None
            latency_ms = (perf_counter() - start) * 1000
            if not text:
                raise RuntimeError("empty response")
            logger.info(
                "llm provider=%s model=%s latency_ms=%.1f success=true",
                self.provider,
                self.model,
                latency_ms,
            )
            return LLMResponse(
                text=text,
                model=self.model,
                provider=self.provider,
                latency_ms=latency_ms,
                raw=raw,
            )
        except Exception as exc:
            latency_ms = (perf_counter() - start) * 1000
            logger.warning(
                "llm provider=%s model=%s latency_ms=%.1f success=false error=%s",
                self.provider,
                self.model,
                latency_ms,
                exc,
            )
            return LLMResponse(
                text="",
                model=self.model,
                provider=self.provider,
                latency_ms=latency_ms,
                error=str(exc),
            )


class CloudLLMAdapter(OpenAICompatibleLLMAdapter):
    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        api_key: str,
        timeout_sec: float = 120.0,
        enabled: bool = True,
    ) -> None:
        super().__init__(
            provider="cloud",
            model=model,
            base_url=base_url,
            api_key=api_key,
            timeout_sec=timeout_sec,
            enabled=enabled,
        )

