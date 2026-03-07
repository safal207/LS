from .capture import PortAudioCapture, WASAPICapture
from .endpoint_detector import EndpointDetector, SpeechSegment
from .frame_buffer import AudioRingBuffer
from .pipeline import StreamingAudioPipeline
from .rust_core import RustAudioCore
from .vad import SileroVAD, WebRTCVAD

try:  # optional dependency path (PyAudio)
    from .audio_module import AudioIngestion
except Exception:  # pragma: no cover
    AudioIngestion = None  # type: ignore

__all__ = [
    "AudioIngestion",
    "PortAudioCapture",
    "WASAPICapture",
    "EndpointDetector",
    "SpeechSegment",
    "AudioRingBuffer",
    "StreamingAudioPipeline",
    "RustAudioCore",
    "SileroVAD",
    "WebRTCVAD",
]
