from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List

from .frame import GlobalFrame


@dataclass
class WorkspaceBus:
    frames: List[GlobalFrame] = field(default_factory=list)
    listeners: List[Callable[[GlobalFrame], None]] = field(default_factory=list)

    def publish(self, frame: GlobalFrame) -> None:
        self.frames.append(frame)
        for listener in list(self.listeners):
            listener(frame)

    def subscribe(self, listener: Callable[[GlobalFrame], None]) -> None:
        self.listeners.append(listener)
