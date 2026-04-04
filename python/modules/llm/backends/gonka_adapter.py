from __future__ import annotations

from .cloud_adapter import OpenAICompatibleLLMAdapter


class GonkaLLMAdapter(OpenAICompatibleLLMAdapter):
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
            provider="gonka",
            model=model,
            base_url=base_url,
            api_key=api_key,
            timeout_sec=timeout_sec,
            enabled=enabled,
        )

