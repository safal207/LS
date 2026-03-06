from __future__ import annotations
import threading
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
import numpy as np

@dataclass
class Frame:
    id: str
    data: np.ndarray
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

class FrameBuffer:
    """Stores a sequence of captured frames for temporal analysis."""
    def __init__(self, max_frames: int = 30):
        self.max_frames = max_frames
        self._frames: List[Frame] = []
        self._lock = threading.Lock()

    def add_frame(self, frame_data: np.ndarray, metadata: Dict[str, Any] = None):
        """Adds a new frame to the buffer."""
        frame_id = f"frame_{int(time.time() * 1000)}"
        new_frame = Frame(id=frame_id, data=frame_data, metadata=metadata or {})
        with self._lock:
            self._frames.append(new_frame)
            if len(self._frames) > self.max_frames:
                self._frames.pop(0)
        return frame_id

    def get_latest_frame(self) -> Optional[Frame]:
        """Returns the most recent frame."""
        with self._lock:
            return self._frames[-1] if self._frames else None

    def get_frame_by_id(self, frame_id: str) -> Optional[Frame]:
        """Returns a frame with the given ID."""
        with self._lock:
            for f in self._frames:
                if f.id == frame_id:
                    return f
            return None

    def get_frame_sequence(self, count: int = 5) -> List[Frame]:
        """Returns a list of the last N frames."""
        with self._lock:
            return self._frames[-count:]

    def clear(self):
        """Clears the buffer."""
        with self._lock:
            self._frames = []
