from __future__ import annotations

from typing import Any, Dict

from .cognitive_reducer import CognitiveReducer
from .cognitive_transaction_log import CognitiveTransactionLog


class CognitiveStore:
    """Materialized cognitive state built from CognitiveTransactionLog."""

    def __init__(self, log: CognitiveTransactionLog, reducer: CognitiveReducer, initial_state: Dict[str, Any] | None = None) -> None:
        self.log = log
        self.reducer = reducer
        self.state: Dict[str, Any] = dict(initial_state or {})
        self.cursor = 0

    def rebuild(self) -> None:
        for tx in self.log.since(self.cursor):
            self.state = self.reducer.apply(self.state, tx)
            self.cursor += 1

    def snapshot(self) -> Dict[str, Any]:
        return self.state
