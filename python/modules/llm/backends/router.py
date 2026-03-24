from __future__ import annotations

import logging
from typing import Optional

from config import (
    GONKA_API_KEY,
    GONKA_BASE_URL,
    GONKA_ENABLED,
    GONKA_MODEL,
    GONKA_TIMEOUT_SEC,
    GROQ_API_KEY,
    GROQ_BASE_URL,
    GROQ_MODEL,
    GROQ_TIMEOUT_SEC,
    LLM_BACKEND,
    LLM_FALLBACK_BACKEND,
    USE_CLOUD_LLM,
    USE_GROQ,
)

from .base import LLMResponse
from .cloud_adapter import CloudLLMAdapter
from .gonka_adapter import GonkaLLMAdapter
from .local_adapter import LocalLLMAdapter

logger = logging.getLogger(__name__)


def _parse_route(value: Optional[str]) -> list[str]:
    if not value:
        return []
    parts = [segment.strip().lower() for segment in str(value).split(",")]
    return [segment for segment in parts if segment]


class LLMBackendRouter:
    def __init__(self, primary: str, fallback_chain: list[str], backends: dict[str, object]) -> None:
        self.primary = primary
        self.fallback_chain = fallback_chain
        self.backends = backends
        self.last_response: Optional[LLMResponse] = None

    @property
    def route(self) -> list[str]:
        ordered = [self.primary] + list(self.fallback_chain)
        seen: set[str] = set()
        result: list[str] = []
        for name in ordered:
            if name and name not in seen and name in self.backends:
                result.append(name)
                seen.add(name)
        return result

    def generate(
        self,
        messages,
        system_prompt=None,
        temperature=None,
        max_tokens=None,
        timeout=None,
        metadata=None,
        *,
        stream: bool = False,
        on_token=None,
    ) -> LLMResponse:
        errors: list[str] = []
        chain = self.route
        for index, backend_name in enumerate(chain):
            backend = self.backends[backend_name]
            response = backend.generate(
                messages=messages,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                metadata=metadata,
                stream=stream,
                on_token=on_token,
            )
            if response.ok:
                if index > 0:
                    response.was_fallback_used = True
                    response.fallback_from = chain[0]
                    response.fallback_to = backend_name
                self.last_response = response
                return response
            errors.append(f"{backend_name}: {response.error or 'unknown error'}")

        final = LLMResponse(
            text="",
            model="",
            provider=chain[0] if chain else "unknown",
            latency_ms=0.0,
            error="; ".join(errors) if errors else "no backend available",
            was_fallback_used=len(chain) > 1,
            fallback_from=chain[0] if len(chain) > 1 else None,
            fallback_to=chain[-1] if len(chain) > 1 else None,
        )
        self.last_response = final
        logger.warning("llm router failed route=%s error=%s", "->".join(chain), final.error)
        return final


def build_llm_backend(
    *,
    local_handler=None,
    local_model: str = "",
    local_fallback_model: str = "",
    backend: Optional[str] = None,
    fallback_chain: Optional[str] = None,
) -> LLMBackendRouter:
    primary = (backend or LLM_BACKEND or "").strip().lower()
    fallbacks = _parse_route(fallback_chain or LLM_FALLBACK_BACKEND)

    if not primary:
        if GONKA_ENABLED and GONKA_API_KEY:
            primary = "gonka"
        elif USE_GROQ or USE_CLOUD_LLM:
            primary = "cloud"
        else:
            primary = "local"

    if not fallbacks:
        if primary == "gonka":
            fallbacks = ["cloud", "local"]
        elif primary == "cloud":
            fallbacks = ["local"]
        else:
            fallbacks = []

    backends: dict[str, object] = {
        "local": LocalLLMAdapter(
            handler=local_handler,
            model=local_model,
            fallback_model=local_fallback_model,
        ),
        "cloud": CloudLLMAdapter(
            model=GROQ_MODEL,
            base_url=GROQ_BASE_URL,
            api_key=GROQ_API_KEY,
            timeout_sec=GROQ_TIMEOUT_SEC,
            enabled=bool(USE_GROQ or USE_CLOUD_LLM or GROQ_API_KEY),
        ),
        "gonka": GonkaLLMAdapter(
            model=GONKA_MODEL,
            base_url=GONKA_BASE_URL,
            api_key=GONKA_API_KEY,
            timeout_sec=GONKA_TIMEOUT_SEC,
            enabled=bool(GONKA_ENABLED and GONKA_API_KEY),
        ),
    }
    return LLMBackendRouter(primary=primary, fallback_chain=fallbacks, backends=backends)

