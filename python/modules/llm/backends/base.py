from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional, Protocol


@dataclass
class LLMResponse:
    text: str
    model: str
    provider: str
    latency_ms: float
    raw: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    was_fallback_used: bool = False
    fallback_from: Optional[str] = None
    fallback_to: Optional[str] = None

    @property
    def ok(self) -> bool:
        return bool(self.text) and not self.error

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LLMBackend(Protocol):
    provider: str
    model: str

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
        ...


def normalize_messages(messages, system_prompt: Optional[str] = None) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    if system_prompt:
        normalized.append({"role": "system", "content": system_prompt})

    if messages is None:
        return normalized
    if isinstance(messages, str):
        normalized.append({"role": "user", "content": messages})
        return normalized

    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role", "user"))
        content = str(message.get("content", ""))
        normalized.append({"role": role, "content": content})
    return normalized

