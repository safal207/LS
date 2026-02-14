from __future__ import annotations

from dataclasses import dataclass, field
from time import time
from typing import Any, Callable

SignalHandler = Callable[["InternalSignal"], None]

CAUSAL_RISK_DETECTED = "causalriskdetected"
CAUSAL_DRIFT = "causal_drift"
CAUSAL_INCONSISTENCY = "causal_inconsistency"


@dataclass
class InternalSignal:
    """Structured internal signal emitted by NCA cognitive components."""

    signal_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    t: int | None = None
    timestamp: float = field(default_factory=time)


class SignalBus:
    """Centralized in-process registry and dispatcher for internal signals."""

    def __init__(self) -> None:
        self._handlers: list[SignalHandler] = []
        self._recent: list[InternalSignal] = []

    def emit(self, signal: InternalSignal) -> None:
        self._recent.append(signal)
        for handler in self._handlers:
            handler(signal)

    def subscribe(self, handler: SignalHandler) -> None:
        self._handlers.append(handler)

    def get_recent(self, *, clear: bool = False) -> list[InternalSignal]:
        snapshot = list(self._recent)
        if clear:
            self._recent.clear()
        return snapshot
