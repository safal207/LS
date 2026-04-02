from __future__ import annotations

import json
import logging
from time import perf_counter
from typing import Any, Optional
from urllib import error, request

from .base import LLMResponse, normalize_messages

logger = logging.getLogger(__name__)


class MimoLLMAdapter:
    provider = "mimo"

    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        api_key: str,
        timeout_sec: float = 120.0,
        enabled: bool = True,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_sec = timeout_sec
        self.enabled = enabled

    def _build_payload(
        self,
        messages,
        system_prompt: Optional[str],
        temperature: Optional[float],
        max_tokens: Optional[int],
    ) -> dict[str, Any]:
        prompt_messages = normalize_messages(messages, system_prompt=system_prompt)
        system_blocks: list[str] = []
        anthropic_messages: list[dict[str, str]] = []
        for message in prompt_messages:
            role = str(message.get("role", "user"))
            content = str(message.get("content", ""))
            if role == "system":
                system_blocks.append(content)
                continue
            anthropic_role = "assistant" if role == "assistant" else "user"
            anthropic_messages.append({"role": anthropic_role, "content": content})
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": int(max_tokens or 1024),
        }
        if system_blocks:
            payload["system"] = "\n\n".join(block for block in system_blocks if block)
        if temperature is not None:
            payload["temperature"] = float(temperature)
        return payload

    def _extract_text(self, body: dict[str, Any]) -> str:
        content = body.get("content")
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
            return "".join(parts).strip()
        if isinstance(content, str):
            return content.strip()
        return ""

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
        _ = metadata, stream, on_token
        start = perf_counter()
        if not self.enabled:
            return LLMResponse(
                text="",
                model=self.model,
                provider=self.provider,
                latency_ms=0.0,
                error="mimo backend disabled",
            )
        if not self.api_key or not self.base_url or not self.model:
            return LLMResponse(
                text="",
                model=self.model,
                provider=self.provider,
                latency_ms=0.0,
                error="mimo backend not configured",
            )

        payload = self._build_payload(messages, system_prompt, temperature, max_tokens)
        endpoints = [f"{self.base_url}/v1/messages", f"{self.base_url}/messages"]
        last_error = "mimo request failed"
        for endpoint in endpoints:
            try:
                req = request.Request(
                    endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}",
                        "anthropic-version": "2023-06-01",
                    },
                    method="POST",
                )
                with request.urlopen(req, timeout=float(timeout or self.timeout_sec)) as resp:
                    body = json.loads(resp.read().decode("utf-8", "ignore"))
                text = self._extract_text(body)
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
                    raw=body,
                )
            except error.HTTPError as exc:
                try:
                    details = exc.read().decode("utf-8", "ignore")
                except Exception:
                    details = str(exc)
                last_error = f"{exc.code}: {details}".strip()
                if exc.code == 404:
                    continue
            except Exception as exc:
                last_error = str(exc)

        latency_ms = (perf_counter() - start) * 1000
        logger.warning(
            "llm provider=%s model=%s latency_ms=%.1f success=false error=%s",
            self.provider,
            self.model,
            latency_ms,
            last_error,
        )
        return LLMResponse(
            text="",
            model=self.model,
            provider=self.provider,
            latency_ms=latency_ms,
            error=last_error,
        )
