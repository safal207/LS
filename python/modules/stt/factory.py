from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import math

from faster_whisper import WhisperModel

try:
    from config import WHISPER_MODEL_SIZE
except Exception:  # pragma: no cover - fallback for alternate runtimes
    WHISPER_MODEL_SIZE = "small"

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


@dataclass
class WhisperAudioBackend:
    """Owns a local Whisper model and transcribes raw audio arrays."""

    model_size: str = WHISPER_MODEL_SIZE
    device: str = "cpu"
    compute_type: str = "int8"
    language: str = "ru"
    beam_size: int = 5
    vad_filter: bool = True
    condition_on_previous_text: bool = False
    temperature: float = 0.0
    download_root: str | None = None
    local_files_only: bool = False

    def __post_init__(self) -> None:
        self.model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
            download_root=self.download_root,
            local_files_only=self.local_files_only,
        )

    def transcribe_audio(self, audio_source: Any) -> dict[str, Any]:
        segments, _info = self.model.transcribe(
            audio_source,
            language=self.language,
            beam_size=self.beam_size,
            temperature=self.temperature,
            vad_filter=self.vad_filter,
            condition_on_previous_text=self.condition_on_previous_text,
            suppress_blank=True,
        )
        text_parts: list[str] = []
        words: list[dict[str, Any]] = []
        chunk_log_probs: list[float] = []
        for segment in segments:
            seg_text = (segment.text or "").strip()
            if seg_text:
                text_parts.append(seg_text)
                if hasattr(segment, "avg_logprob") and segment.avg_logprob is not None:
                    chunk_log_probs.append(float(segment.avg_logprob))
            if getattr(segment, "words", None):
                for word in segment.words:
                    word_text = (getattr(word, "word", "") or "").strip()
                    if word_text:
                        words.append({
                            "word": word_text,
                            "probability": round(float(getattr(word, "probability", 0.0)), 4),
                        })
        text = " ".join(text_parts).strip()
        avg_logprob = sum(chunk_log_probs) / len(chunk_log_probs) if chunk_log_probs else -10.0
        asr_confidence = round(math.exp(max(avg_logprob, -10.0)), 4)
        return {
            "type": "question",
            "text": text,
            "words": words,
            "_words": words,
            "_chunk_log_probs": chunk_log_probs,
            "_asr_confidence": asr_confidence,
            "source": "local_stt",
            "confidence": asr_confidence,
        }


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


def build_local_whisper_adapter(
    *,
    model_size: str = WHISPER_MODEL_SIZE,
    device: str = "cpu",
    compute_type: str = "int8",
    language: str = "ru",
    vad_filter: bool = True,
    beam_size: int = 5,
    condition_on_previous_text: bool = False,
    temperature: float = 0.0,
    download_root: str | None = None,
    local_files_only: bool = False,
) -> LocalWhisperAdapter:
    """Create a local Whisper-backed STT adapter without exposing WhisperModel to callers."""
    backend = WhisperAudioBackend(
        model_size=model_size,
        device=device,
        compute_type=compute_type,
        language=language,
        beam_size=beam_size,
        vad_filter=vad_filter,
        condition_on_previous_text=condition_on_previous_text,
        temperature=temperature,
        download_root=download_root,
        local_files_only=local_files_only,
    )
    return LocalWhisperAdapter(engine=backend, name=f"local_whisper:{model_size}")
