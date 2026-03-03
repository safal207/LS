from __future__ import annotations
import logging
import threading
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

class AttentionPolicy:
    """Manages attention budget and model escalation logic."""
    def __init__(self, max_requests_per_min: int = 5):
        self.max_requests_per_min = max_requests_per_min
        self._request_timestamps: List[float] = []
        self._lock = threading.Lock()

    def can_request(self) -> bool:
        """Checks if there's enough attention budget for a model request."""
        now = time.time()
        with self._lock:
            # Filter timestamps from the last minute
            self._request_timestamps = [t for t in self._request_timestamps if now - t < 60]

            if len(self._request_timestamps) < self.max_requests_per_min:
                self._request_timestamps.append(now)
                return True
            return False

    def select_model(self, scene_score: float, confusion_score: float) -> str:
        """Selects between Qwen-2B (light) and 9B (heavy) based on importance."""
        # 2B for "cheap" tasks, 9B for high-value interventions
        if scene_score > 0.8 or confusion_score > 0.7:
            return "9B" # Escalation to heavy model
        return "2B" # Default light model

class AutoTrigger:
    """Decides when to proactively perform deep visual analysis."""
    def __init__(self, threshold: float = 0.5):
        self.trigger_threshold = threshold
        self._last_trigger_time = 0.0
        self._cooldown = 10.0 # 10 seconds cooldown between triggers

    def should_trigger(self, scene_score: float, confusion_score: float) -> bool:
        """Determines if a proactive intervention is needed."""
        now = time.time()
        if now - self._last_trigger_time < self._cooldown:
            return False

        # Simple v0.1: Trigger if scene changed significantly OR user is confused
        if scene_score > 0.7 or confusion_score > self.trigger_threshold:
            self._last_trigger_time = now
            return True
        return False
