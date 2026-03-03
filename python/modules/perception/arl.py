from __future__ import annotations
import logging
import threading
import time
from typing import List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class VisualHint:
    id: str
    type: str # "Hint", "Option", "Brief"
    content: str
    grounding_refs: List[str] # List of Frame IDs or OCR fragments
    timestamp: float = field(default_factory=time.time)
    ttl: float = 8.0 # Default TTL of 8 seconds for Hint

class CognitiveOverlay:
    """Manages visual hints and suggestions delivered to the user."""
    def __init__(self):
        self._hints: List[VisualHint] = []
        self._lock = threading.Lock()

    def add_hint(self, hint_type: str, content: str, grounding: List[str]):
        """Creates and adds a new visual hint."""
        hint_id = f"hint_{int(time.time() * 1000)}"
        new_hint = VisualHint(id=hint_id, type=hint_type, content=content, grounding_refs=grounding)
        with self._lock:
            self._hints.append(new_hint)
            if len(self._hints) > 20:
                self._hints.pop(0)
        return hint_id

    def get_active_hints(self) -> List[VisualHint]:
        """Returns hints that haven't expired based on their TTL."""
        now = time.time()
        with self._lock:
            # Filter expired hints
            self._hints = [h for h in self._hints if now - h.timestamp < h.ttl]
            return list(self._hints)

    def select_best_hint(self) -> Optional[VisualHint]:
        """Chooses the most relevant or recent hint for display."""
        active_hints = self.get_active_hints()
        if not active_hints:
            return None
        # For simplicity, return the most recent one
        return active_hints[-1]

    def clear(self):
        with self._lock:
            self._hints = []
