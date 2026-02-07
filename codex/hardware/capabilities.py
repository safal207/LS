from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Set

from codex.registry.model_config import ModelConfig

from .profiler import HardwareProfile


MEMORY_MULTIPLIERS = {
    "kb": 1 / 1024,
    "mb": 1,
    "gb": 1024,
    "tb": 1024 * 1024,
}


def parse_memory_to_mb(value: str | None) -> float | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    for unit, multiplier in MEMORY_MULTIPLIERS.items():
        if normalized.endswith(unit):
            number = normalized[: -len(unit)].strip()
            return float(number) * multiplier
    return float(normalized)


@dataclass(frozen=True)
class HardwareCapabilities:
    profile: HardwareProfile

    @property
    def gpu_available(self) -> bool:
        return self.profile.gpu is not None

    @property
    def fp16_available(self) -> bool:
        return self.profile.torch.fp16

    @property
    def bf16_available(self) -> bool:
        return self.profile.torch.bf16

    @property
    def int8_available(self) -> bool:
        return True

    def max_model_size_mb(self) -> float:
        buffer_mb = 512
        return max(self.profile.ram_available_mb - buffer_mb, 0)

    def max_context_tokens(self) -> int:
        if self.profile.ram_available_mb >= 32768:
            return 8192
        if self.profile.ram_available_mb >= 16384:
            return 4096
        if self.profile.ram_available_mb >= 8192:
            return 2048
        return 1024

    def allowed_quants(self) -> Set[str]:
        allowed = {"int8", "q4", "q5"}
        if self.fp16_available:
            allowed.add("fp16")
        if self.bf16_available:
            allowed.add("bf16")
        return allowed

    def supports_whisper_medium(self) -> bool:
        return self.profile.ram_available_mb >= 2048

    def supports_llama_3b(self) -> bool:
        return self.profile.ram_available_mb >= 4096 and self.gpu_available

    def supports_model(self, model: ModelConfig | dict) -> bool:
        config = model if isinstance(model, ModelConfig) else ModelConfig.from_dict("_", model)
        ram_required = parse_memory_to_mb(config.ram_required)
        if ram_required is not None and self.profile.ram_available_mb < ram_required:
            return False
        if config.device == "gpu" and not self.gpu_available:
            return False
        if config.quant in {"fp16", "float16"} and not self.fp16_available:
            return False
        if config.quant in {"bf16", "bfloat16"} and not self.bf16_available:
            return False
        if config.quant in {"int8", "q8"} and not self.int8_available:
            return False
        return True

    def filter_supported(self, models: Iterable[ModelConfig]) -> list[ModelConfig]:
        return [model for model in models if self.supports_model(model)]
