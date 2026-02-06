from __future__ import annotations

import time
from typing import Callable

from .state import FieldNodeState, FieldState


class FieldRegistry:
    def __init__(self, ttl: float = 5.0, *, clock: Callable[[], float] | None = None) -> None:
        self.ttl = ttl
        self._clock = clock or time.time
        self._nodes: dict[str, FieldNodeState] = {}

    def update_node(self, node_state: FieldNodeState) -> None:
        self._nodes[node_state.node_id] = node_state
        self._prune()

    def get_state(self) -> FieldState:
        self._prune()
        return FieldState(nodes=dict(self._nodes))

    def _prune(self) -> None:
        now = self._clock()
        expired = [node_id for node_id, state in self._nodes.items() if now - state.timestamp > self.ttl]
        for node_id in expired:
            self._nodes.pop(node_id, None)
