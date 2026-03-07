from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np


@dataclass
class SpeechSegment:
    samples: np.ndarray
    start_frame: int
    end_frame: int


@dataclass
class EndpointDetector:
    """Builds speech segments using VAD decisions and silence timeout.

    Default: 20ms frames, endpoint after 600ms silence.
    """

    frame_ms: int = 20
    silence_ms_to_endpoint: int = 600
    min_speech_ms: int = 120
    _in_speech: bool = False
    _speech_frames: List[np.ndarray] = field(default_factory=list)
    _speech_start_frame: Optional[int] = None
    _trailing_silence_frames: int = 0

    def process_frame(self, frame: np.ndarray, is_speech: bool, frame_index: int) -> Optional[SpeechSegment]:
        silence_frames_limit = max(1, self.silence_ms_to_endpoint // self.frame_ms)
        min_speech_frames = max(1, self.min_speech_ms // self.frame_ms)

        if is_speech:
            if not self._in_speech:
                self._in_speech = True
                self._speech_start_frame = frame_index
                self._speech_frames.clear()
            self._speech_frames.append(frame)
            self._trailing_silence_frames = 0
            return None

        if self._in_speech:
            self._speech_frames.append(frame)
            self._trailing_silence_frames += 1

            if self._trailing_silence_frames >= silence_frames_limit:
                total_frames = len(self._speech_frames)
                if total_frames >= min_speech_frames:
                    samples = np.concatenate(self._speech_frames)
                    segment = SpeechSegment(
                        samples=samples,
                        start_frame=int(self._speech_start_frame or frame_index),
                        end_frame=frame_index,
                    )
                else:
                    segment = None
                self._reset_state()
                return segment

        return None

    def flush(self, frame_index: int) -> Optional[SpeechSegment]:
        if not self._in_speech or not self._speech_frames:
            return None
        segment = SpeechSegment(
            samples=np.concatenate(self._speech_frames),
            start_frame=int(self._speech_start_frame or frame_index),
            end_frame=frame_index,
        )
        self._reset_state()
        return segment

    def _reset_state(self) -> None:
        self._in_speech = False
        self._speech_frames.clear()
        self._speech_start_frame = None
        self._trailing_silence_frames = 0
