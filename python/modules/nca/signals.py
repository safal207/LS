from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from threading import Lock
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


@dataclass
class SignalBusMetrics:
    """Operational counters for deterministic signal processing."""

    total_emitted: int = 0
    total_processed: int = 0
    total_dropped: int = 0
    max_pending_seen: int = 0


class DeterministicSignalBus(CollectiveSignalBus):
    """Deterministic, FIFO, non-reentrant signal bus with per-tick batching."""

    def __init__(self, *, max_signals_per_tick: int = 10_000) -> None:
        """Initialize deterministic bus with bounded per-tick processing.

        Args:
            max_signals_per_tick: Maximum signals processed in a single `process_tick()` call.
                - 1_000: low-latency, small meshes (<100 agents)
                - 10_000: default, medium meshes (100-1000 agents)
                - 100_000: high-throughput, large meshes (1000+ agents)

        Note:
            Signals over the per-tick limit remain queued for subsequent ticks.
            Monitor `metrics.max_pending_seen` and pending queue size to tune capacity.
        """
        super().__init__()
        self._pending: deque[tuple[str, InternalSignal, dict[str, str]]] = deque()
        self._processing: bool = False
        self._lock = Lock()
        self.max_signals_per_tick = max_signals_per_tick
        self.metrics = SignalBusMetrics()

    def _enqueue(self, mode: str, signal: InternalSignal, kwargs: dict[str, str]) -> None:
        with self._lock:
            self.metrics.total_emitted += 1
            self._pending.append((mode, signal, kwargs))
            self.metrics.max_pending_seen = max(self.metrics.max_pending_seen, len(self._pending))

    def emit_local(self, signal: InternalSignal, *, target_agent_id: str) -> None:
        self._enqueue("local", signal, {"target_agent_id": target_agent_id})

    def emit_group(self, signal: InternalSignal, *, group_id: str) -> None:
        self._enqueue("group", signal, {"group_id": group_id})

    def emit_broadcast(self, signal: InternalSignal) -> None:
        self._enqueue("broadcast", signal, {})

    def emit(self, signal: InternalSignal) -> None:
        self._enqueue("broadcast", signal, {})

    def process_tick(self) -> list[InternalSignal]:
        with self._lock:
            if self._processing:
                return []
            self._processing = True

        processed: list[InternalSignal] = []
        try:
            while len(processed) < self.max_signals_per_tick:
                with self._lock:
                    if not self._pending:
                        break
                    mode, signal, kwargs = self._pending.popleft()
                processed.append(signal)
                if mode == "local":
                    super().emit_local(signal, target_agent_id=kwargs["target_agent_id"])
                elif mode == "group":
                    super().emit_group(signal, group_id=kwargs["group_id"])
                else:
                    super().emit_broadcast(signal)
        finally:
            with self._lock:
                self.metrics.total_processed += len(processed)
                self._processing = False

        return processed
