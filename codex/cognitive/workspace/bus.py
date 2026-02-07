from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List


@dataclass
class WorkspaceBus:
    frames: List[Any] = field(default_factory=list)
    listeners: List[Callable[[Any], None]] = field(default_factory=list)

    def publish(self, frame: Any) -> None:
        self.frames.append(frame)
        # Safe iteration in case listeners modify the list during callbacks
        for listener in list(self.listeners):
            listener(frame)

    def subscribe(self, listener: Callable[[Any], None]) -> None:
        self.listeners.append(listener)
