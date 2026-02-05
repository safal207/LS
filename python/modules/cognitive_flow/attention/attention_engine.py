from __future__ import annotations

from typing import Any, Dict

from .attention_state import AttentionState


class AttentionEngine:
    def __init__(self) -> None:
        self.state = AttentionState()

    def update(self, presence: Any, metrics: Dict[str, Any] | None = None) -> AttentionState:
        """
        v0.1 stub: returns the current attention state.
        Future versions will use presence + metrics to adjust focus.
        """
        return self.state
