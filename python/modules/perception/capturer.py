from __future__ import annotations
import logging
import threading
import time
from typing import Optional, Dict, Any, List
import numpy as np
from PIL import Image
try:
    import mss
except ImportError:
    mss = None
import io

logger = logging.getLogger(__name__)

class ScreenCapturer:
    """Captures the current screen content."""
    def __init__(self, monitor_index: int = 1):
        self.monitor_index = monitor_index
        self._lock = threading.Lock()
        self.sct = None
        if mss:
            try:
                self.sct = mss.mss()
            except Exception as e:
                logger.warning(f"Failed to initialize mss: {e}")

    def capture_frame(self) -> Optional[np.ndarray]:
        """Captures a frame from the screen and returns it as a numpy array."""
        if not self.sct:
             # Return a mock frame if mss is not available (e.g., in CI/headless)
             return np.zeros((1080, 1920, 3), dtype=np.uint8)

        try:
            # For simplicity, we capture the primary monitor
            if self.monitor_index >= len(self.sct.monitors):
                monitor = self.sct.monitors[0]
            else:
                monitor = self.sct.monitors[self.monitor_index]

            sct_img = self.sct.grab(monitor)
            # Convert to RGB numpy array
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            return np.array(img)
        except Exception as e:
            logger.error(f"Error capturing screen frame: {e}")
            return None

    def get_frame_metadata(self) -> Dict[str, Any]:
        """Returns metadata about the captured frame."""
        monitors = self.sct.monitors if self.sct else [{"left":0, "top":0, "width":1920, "height":1080}]
        idx = self.monitor_index if self.sct and self.monitor_index < len(monitors) else 0

        return {
            "monitor_index": idx,
            "timestamp": time.time(),
            "dimensions": monitors[idx]
        }
