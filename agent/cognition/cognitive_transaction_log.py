from __future__ import annotations

from typing import List

from .cognitive_event_mesh import CognitiveEventMesh
from .cognitive_transaction import CognitiveTransaction


class CognitiveTransactionLog:
    """Append-only cognitive transaction log."""

    def __init__(self, event_mesh: CognitiveEventMesh | None = None) -> None:
        self._transactions: List[CognitiveTransaction] = []
        self._event_mesh = event_mesh

    def append(self, tx: CognitiveTransaction) -> None:
        self._transactions.append(tx)
        if self._event_mesh is not None:
            self._event_mesh.publish(tx)

    def all(self) -> List[CognitiveTransaction]:
        return list(self._transactions)

    def since(self, index: int) -> List[CognitiveTransaction]:
        return list(self._transactions[max(0, index):])

    def size(self) -> int:
        return len(self._transactions)
