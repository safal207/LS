from __future__ import annotations
import logging
import queue
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import time

logger = logging.getLogger(__name__)

@dataclass
class PerceptionEvent:
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

@dataclass
class CortexIntent:
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

class PerceptionEventBus:
    """Low-level event bus for raw perception data."""
    def __init__(self):
        self._subscribers: List[Callable[[PerceptionEvent], None]] = []
        self._lock = threading.Lock()

    def subscribe(self, callback: Callable[[PerceptionEvent], None]):
        with self._lock:
            self._subscribers.append(callback)

    def emit(self, event_type: str, payload: Dict[str, Any]):
        event = PerceptionEvent(type=event_type, payload=payload)
        with self._lock:
            subscribers = list(self._subscribers)
        for sub in subscribers:
            try:
                sub(event)
            except Exception as e:
                logger.error(f"Error in PerceptionEventBus subscriber: {e}")

class CortexIntentBus:
    """High-level bus for cognitive intentions."""
    def __init__(self):
        self._subscribers: List[Callable[[CortexIntent], None]] = []
        self._lock = threading.Lock()

    def subscribe(self, callback: Callable[[CortexIntent], None]):
        with self._lock:
            self._subscribers.append(callback)

    def emit(self, intent_type: str, payload: Dict[str, Any]):
        intent = CortexIntent(type=intent_type, payload=payload)
        with self._lock:
            subscribers = list(self._subscribers)
        for sub in subscribers:
            try:
                sub(intent)
            except Exception as e:
                logger.error(f"Error in CortexIntentBus subscriber: {e}")
