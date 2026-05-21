from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from shared.operator_schema import OperatorUtterance, ensure_operator_item


class STTAdapter(Protocol):
    """Common speech-to-text adapter contract."""

    name: str

    def transcribe_audio(self, audio_source: Any) -> dict[str, Any]:
        ...


@dataclass
class LocalWhisperAdapter:
    """Thin adapter over an existing local Whisper-backed STT engine."""

    engine: Any
    name: str = "local_whisper"

    def transcribe_audio(self, audio_source: Any) -> dict[str, Any]:
        if hasattr(self.engine, "transcribe_audio"):
            result = self.engine.transcribe_audio(audio_source)
        elif callable(self.engine):
            result = self.engine(audio_source)
        else:
            raise TypeError("LocalWhisperAdapter.engine must be callable or expose transcribe_audio()")
        return ensure_operator_item(result, default_source="local_stt")


@dataclass
class CloudSTTAdapter:
    """Cloud ASR stub.

    This is intentionally backend-agnostic. Plug in a provider-specific callable
    or client later without changing SmartEar / AgentLoop contracts.
    """

    transcribe_fn: Callable[[Any], dict[str, Any]] | None = None
    name: str = "cloud_asr"
    provider: str = "unknown"
    model: str = "unknown"

    def transcribe_audio(self, audio_source: Any) -> dict[str, Any]:
        if self.transcribe_fn is None:
            raise NotImplementedError(
                "CloudSTTAdapter is a stub. Provide transcribe_fn to enable a cloud ASR backend."
            )
        result = self.transcribe_fn(audio_source)
        item = ensure_operator_item(result, default_source="cloud_stt")
        item["source"] = "cloud_stt"
        item.setdefault("provider", self.provider)
        item.setdefault("model", self.model)
        return item


@dataclass
class FallbackSTTAdapter:
    """Try local STT first, then cloud STT when confidence is too low."""

    local: STTAdapter
    cloud: STTAdapter | None = None
    confidence_floor: float = 0.6
    name: str = "fallback_stt"

    def transcribe_audio(self, audio_source: Any) -> dict[str, Any]:
        local_item = ensure_operator_item(self.local.transcribe_audio(audio_source), default_source="local_stt")
        confidence = float(local_item.get("_asr_confidence", local_item.get("confidence", 0.0)) or 0.0)
        if self.cloud is None or confidence >= self.confidence_floor:
            local_item.setdefault("backend_choice", "local")
            return local_item

        cloud_item = ensure_operator_item(self.cloud.transcribe_audio(audio_source), default_source="cloud_stt")
        cloud_item.setdefault("backend_choice", "cloud")
        cloud_item.setdefault("fallback_reason", f"local_confidence_below_{self.confidence_floor:.2f}")
        return cloud_item


def build_operator_utterance(
    text: str,
    *,
    confidence: float = 0.0,
    source: str = "unknown",
    words: list[dict[str, Any]] | None = None,
    clean_text: str | None = None,
) -> dict[str, Any]:
    """Convenience constructor for adapter outputs."""
    return OperatorUtterance(
        type="question",
        text=text,
        confidence=confidence,
        source=source,
        words=words or [],
        clean_text=clean_text or text,
    ).to_item()
