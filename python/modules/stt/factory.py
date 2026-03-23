from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

try:
    from config import WHISPER_MODEL_SIZE
except ImportError:  # pragma: no cover - package-relative fallback
    from ..config import WHISPER_MODEL_SIZE

from .adapters import CloudSTTAdapter, FallbackSTTAdapter, LocalWhisperAdapter, STTAdapter


@dataclass(frozen=True)
class STTFactoryConfig:
    """Minimal config surface for selecting the STT backend."""

    profile: str = "manual-small"
    confidence_floor: float = 0.6
    use_cloud: bool = False
    cloud_provider: str = "unknown"
    cloud_model: str = "unknown"
    local_model_size: str = WHISPER_MODEL_SIZE


def build_stt_adapter(
    local_engine: Any,
    *,
    config: STTFactoryConfig | None = None,
    cloud_transcribe_fn: Callable[[Any], dict[str, Any]] | None = None,
) -> STTAdapter:
    """Build a local, fallback, or cloud-capable STT adapter.

    The returned object is intentionally backend-agnostic for SmartEar and
    AgentLoop. The caller chooses the local engine, and the factory only wires
    fallback policy.
    """
    cfg = config or STTFactoryConfig()
    local = LocalWhisperAdapter(engine=local_engine, name=f"local_whisper:{cfg.local_model_size}")

    if cfg.use_cloud:
        cloud = CloudSTTAdapter(
            transcribe_fn=cloud_transcribe_fn,
            provider=cfg.cloud_provider,
            model=cfg.cloud_model,
        )
        return FallbackSTTAdapter(
            local=local,
            cloud=cloud,
            confidence_floor=cfg.confidence_floor,
            name=f"fallback:{cfg.profile}",
        )

    if cfg.profile.startswith("manual"):
        return local

    if cfg.profile.startswith("auto"):
        return FallbackSTTAdapter(
            local=local,
            cloud=None,
            confidence_floor=cfg.confidence_floor,
            name=f"fallback:{cfg.profile}",
        )

    return local
