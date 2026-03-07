try:
    from .stt_module import SpeechToText
except ImportError:  # pragma: no cover
    SpeechToText = None  # type: ignore

from .stt_streaming import MockStreamingSTT, StreamingWhisperSTT

__all__ = ["SpeechToText", "StreamingWhisperSTT", "MockStreamingSTT"]
