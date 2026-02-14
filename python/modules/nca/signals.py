from __future__ import annotations

from dataclasses import dataclass, field
from time import time
from typing import Any, Callable

SignalHandler = Callable[["InternalSignal"], None]

CAUSAL_RISK_DETECTED = "causalriskdetected"
CAUSAL_DRIFT = "causal_drift"
CAUSAL_INCONSISTENCY = "causal_inconsistency"
COLLECTIVE_RISK_DETECTED = "collective_risk_detected"
COORDINATION_REQUIRED = "coordination_required"
MULTIAGENT_DRIFT = "multiagent_drift"
COLLECTIVE_GOAL_CONFLICT = "collectivegoalconflict"


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


class CollectiveSignalBus(SignalBus):
    """Signal bus with scoped routing for multi-agent communication."""

    def __init__(self) -> None:
        super().__init__()
        self._agent_handlers: dict[str, list[SignalHandler]] = {}
        self._group_handlers: dict[str, list[SignalHandler]] = {}

    def subscribe_agent(self, agent_id: str, handler: SignalHandler) -> None:
        self._agent_handlers.setdefault(agent_id, []).append(handler)

    def subscribe_group(self, group_id: str, handler: SignalHandler) -> None:
        self._group_handlers.setdefault(group_id, []).append(handler)

    def emit_local(self, signal: InternalSignal, *, target_agent_id: str) -> None:
        signal.payload.setdefault("scope", "local")
        signal.payload.setdefault("targetagentid", target_agent_id)
        self._recent.append(signal)
        for handler in self._agent_handlers.get(target_agent_id, []):
            handler(signal)
        for handler in self._handlers:
            handler(signal)

    def emit_group(self, signal: InternalSignal, *, group_id: str) -> None:
        signal.payload.setdefault("scope", "group")
        signal.payload.setdefault("groupid", group_id)
        self._recent.append(signal)
        for handler in self._group_handlers.get(group_id, []):
            handler(signal)
        for handler in self._handlers:
            handler(signal)

    def emit_broadcast(self, signal: InternalSignal) -> None:
        signal.payload.setdefault("scope", "broadcast")
        self._recent.append(signal)
        delivered: set[int] = set()
        for handlers in self._agent_handlers.values():
            for handler in handlers:
                handler_id = id(handler)
                if handler_id in delivered:
                    continue
                delivered.add(handler_id)
                handler(signal)
        for handler in self._handlers:
            handler(signal)

    def emit(self, signal: InternalSignal) -> None:
        source = signal.payload.get("sourceagentid")
        if source is None:
            signal.payload["sourceagentid"] = "system"
        self.emit_broadcast(signal)
