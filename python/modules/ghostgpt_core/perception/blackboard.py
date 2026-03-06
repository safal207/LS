from __future__ import annotations
import threading
import time
from typing import Any, Dict, List
from dataclasses import dataclass, field

@dataclass
class VisualFact:
    fact: str
    confidence: float
    source_frame_id: str
    timestamp: float = field(default_factory=time.time)

class SessionBlackboard:
    """The single source of truth for the current perception state."""
    def __init__(self):
        self._lock = threading.Lock()
        self._mode: str = "Idle"
        self._facts: List[VisualFact] = []
        self._metadata: Dict[str, Any] = {}
        self._last_update: float = time.time()

    def update_mode(self, mode: str):
        with self._lock:
            self._mode = mode
            self._last_update = time.time()

    @property
    def current_mode(self) -> str:
        with self._lock:
            return self._mode

    def add_fact(self, fact: str, confidence: float, frame_id: str):
        new_fact = VisualFact(fact=fact, confidence=confidence, source_frame_id=frame_id)
        with self._lock:
            self._facts.append(new_fact)
            # Keep only recent or relevant facts (e.g., last 50)
            if len(self._facts) > 50:
                self._facts.pop(0)
            self._last_update = time.time()

    def get_facts(self) -> List[VisualFact]:
        with self._lock:
            return list(self._facts)

    def set_metadata(self, key: str, value: Any):
        with self._lock:
            self._metadata[key] = value
            self._last_update = time.time()

    def get_metadata(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._metadata.get(key, default)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "mode": self._mode,
                "facts": [
                    {"fact": f.fact, "confidence": f.confidence, "frame_id": f.source_frame_id}
                    for f in self._facts
                ],
                "metadata": dict(self._metadata),
                "last_update": self._last_update
            }
