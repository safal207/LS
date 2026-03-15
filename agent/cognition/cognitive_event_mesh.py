from __future__ import annotations

from typing import Callable, List

from .cognitive_transaction import CognitiveTransaction


class CognitiveEventMesh:
    """In-memory pub/sub mesh for cognitive transactions."""

    def __init__(self) -> None:
        self._handlers: List[Callable[[CognitiveTransaction], None]] = []

    def publish(self, tx: CognitiveTransaction) -> None:
        for handler in list(self._handlers):
            handler(tx)

    def subscribe(self, handler: Callable[[CognitiveTransaction], None]) -> None:
        self._handlers.append(handler)
