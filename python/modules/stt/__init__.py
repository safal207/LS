try:
    from .stt_module import SpeechToText
except Exception:  # pragma: no cover
    SpeechToText = None  # type: ignore

from .stt_streaming import MockStreamingSTT, StreamingWhisperSTT

__all__ = ["SpeechToText", "StreamingWhisperSTT", "MockStreamingSTT"]
