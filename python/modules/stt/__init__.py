from __future__ import annotations

from .adapters import (
    STTAdapter,
    LocalWhisperAdapter,
    CloudSTTAdapter,
    FallbackSTTAdapter,
    build_operator_utterance,
)
from .factory import STTFactoryConfig, build_stt_adapter

__all__ = [
    "SpeechToText",
    "STTAdapter",
    "LocalWhisperAdapter",
    "CloudSTTAdapter",
    "FallbackSTTAdapter",
    "build_operator_utterance",
    "STTFactoryConfig",
    "build_stt_adapter",
]


def __getattr__(name: str):
    if name == "SpeechToText":
        from .stt_module import SpeechToText
        return SpeechToText
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
