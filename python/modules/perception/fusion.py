from __future__ import annotations
import logging
import threading
from typing import List, Optional
import numpy as np
from PIL import Image
import imagehash
from skimage.metrics import structural_similarity as ssim
import cv2

logger = logging.getLogger(__name__)

class SceneChangeDetector:
    """Analyzes visual changes between consecutive frames."""
    def __init__(self):
        self._last_frame_data: Optional[np.ndarray] = None
        self._last_phash: Optional[imagehash.ImageHash] = None
        self._last_ocr_text: Optional[str] = None

    def calculate_scene_score(
        self,
        current_frame: np.ndarray,
        current_ocr_text: str = ""
    ) -> float:
        """Calculates the scene change score using pHash, SSIM, and OCR delta."""
        if self._last_frame_data is None:
            self._last_frame_data = current_frame
            self._last_phash = imagehash.phash(Image.fromarray(current_frame))
            self._last_ocr_text = current_ocr_text
            return 1.0 # First frame is 1.0 (full change)

        # 1. pHash delta
        current_phash = imagehash.phash(Image.fromarray(current_frame))
        # pHash delta is the Hamming distance, normalize to 0.0-1.0
        phash_delta = (current_phash - self._last_phash) / 64.0

        # 2. SSIM (1.0 is similar, 0.0 is different)
        # Convert to grayscale for SSIM
        current_gray = cv2.cvtColor(current_frame, cv2.COLOR_RGB2GRAY)
        last_gray = cv2.cvtColor(self._last_frame_data, cv2.COLOR_RGB2GRAY)

        # Ensure dimensions match (they should from mss capture)
        if current_gray.shape != last_gray.shape:
             last_gray = cv2.resize(last_gray, (current_gray.shape[1], current_gray.shape[0]))

        score_ssim, _ = ssim(current_gray, last_gray, full=True)
        ssim_diff = 1.0 - score_ssim

        # 3. OCR delta
        # A simple string edit distance could be used, but for v0.1:
        # We just check if OCR text changed significantly
        ocr_delta = 0.0
        if current_ocr_text and self._last_ocr_text:
            if current_ocr_text != self._last_ocr_text:
                ocr_delta = 1.0 # Significant change in text content

        # Formula: scene_score = 0.45 * pHash_delta + 0.35 * (1 - SSIM) + 0.20 * OCR_delta
        scene_score = (0.45 * phash_delta) + (0.35 * ssim_diff) + (0.20 * ocr_delta)

        # Update last values
        self._last_frame_data = current_frame
        self._last_phash = current_phash
        self._last_ocr_text = current_ocr_text

        return float(max(0.0, min(1.0, scene_score)))

class RhythmAnalyzer:
    """Classifies activities based on temporal change patterns."""
    def __init__(self):
        self._scene_scores: List[float] = []
        self._window_size = 10 # last 10 scores
        self._lock = threading.Lock()

    def add_score(self, score: float):
        with self._lock:
            self._scene_scores.append(score)
            if len(self._scene_scores) > self._window_size:
                self._scene_scores.pop(0)

    def classify_mode(self) -> str:
        """Analyzes scene change rhythm to classify activity."""
        with self._lock:
            if not self._scene_scores:
                return "Idle"

            avg_score = sum(self._scene_scores) / len(self._scene_scores)

            # Simple heuristics for v0.1
            if avg_score > 0.6:
                return "Presentation" # High change (slides moving rapidly, or video)
            elif avg_score > 0.2:
                return "Coding" # Moderate change (scrolling, typing)
            else:
                return "Discussion" # Low change (static windows, talking)
