from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from itertools import islice
import logging
import math
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

logger = logging.getLogger(__name__)


try:
    from ncafuzzycore import PyBusConfig as RustPyBusConfig
    from ncafuzzycore import PySignalMetrics as RustPySignalMetrics
    from ncafuzzycore import compute_adjustments as rust_compute_adjustments

    HAS_RUST_FUZZY = True
except ImportError:
    RustPyBusConfig = None
    RustPySignalMetrics = None
    rust_compute_adjustments = None
    HAS_RUST_FUZZY = False


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
    queue_size: int = 0
    tickswithdropped_signals: int = 0
    avgbatchsize: float = 0.0
    queuepeakper_tick: int = 0
    processed_ticks: int = 0


class FuzzyLoadRegulator:
    """Fuzzy regulator for adaptive deterministic bus capacity and priority tuning."""

    def __init__(
        self,
        *,
        min_signals_per_tick: int = 1_000,
        max_signals_per_tick: int = 100_000,
        min_queue_size: int = 10_000,
        max_queue_size: int = 1_000_000,
    ) -> None:
        self.min_signals_per_tick = min_signals_per_tick
        self.max_signals_per_tick = max_signals_per_tick
        self.min_queue_size = min_queue_size
        self.max_queue_size = max_queue_size

    @staticmethod
    def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
        return max(low, min(high, value))

    @staticmethod
    def _ramp_up(value: float, start: float, end: float) -> float:
        if value <= start:
            return 0.0
        if value >= end:
            return 1.0
        return (value - start) / (end - start)

    @staticmethod
    def _ramp_down(value: float, start: float, end: float) -> float:
        if value <= start:
            return 1.0
        if value >= end:
            return 0.0
        return 1.0 - ((value - start) / (end - start))

    @staticmethod
    def _triangular(value: float, left: float, peak: float, right: float) -> float:
        if value <= left or value >= right:
            return 0.0
        if math.isclose(value, peak):
            return 1.0
        if value < peak:
            return (value - left) / (peak - left)
        return (right - value) / (right - peak)

    def compute_adjustments(
        self,
        metrics: SignalBusMetrics,
        *,
        current_max_signals_per_tick: int,
        current_max_queue_size: int,
    ) -> dict[str, float]:
        queue_load = self._clamp(metrics.queue_size / max(1, current_max_queue_size))
        batch_efficiency = self._clamp(metrics.avgbatchsize / max(1, current_max_signals_per_tick))
        burst_pressure = self._clamp(metrics.queuepeakper_tick / max(1, current_max_queue_size))
        drop_rate = self._clamp(metrics.total_dropped / max(1, metrics.total_emitted))

        queue_low = self._ramp_down(queue_load, 0.0, 0.3)
        queue_high = self._ramp_up(queue_load, 0.6, 1.0)
        batch_underutilized = self._ramp_down(batch_efficiency, 0.0, 0.4)
        batch_optimal = self._triangular(batch_efficiency, 0.3, 0.55, 0.8)
        burst_storm = self._ramp_up(burst_pressure, 0.6, 1.0)
        burst_calm = self._ramp_down(burst_pressure, 0.0, 0.2)
        drop_low = self._ramp_down(drop_rate, 0.0, 0.05)
        drop_critical = self._ramp_up(drop_rate, 0.05, 1.0)

        throughput_increase = min(queue_high, batch_optimal)
        throughput_decrease = min(queue_low, batch_underutilized)

        throughput_factor = 1.0
        throughput_factor += 0.35 * throughput_increase
        throughput_factor -= 0.15 * throughput_decrease
        throughput_factor -= 0.60 * drop_critical
        throughput_factor = self._clamp(throughput_factor, 0.4, 1.6)

        queue_factor = 1.0
        queue_factor += 0.25 * min(burst_storm, drop_low)
        queue_factor -= 0.10 * min(queue_low, burst_calm)
        queue_factor = self._clamp(queue_factor, 0.7, 1.4)

        priority_boost = 1.0
        priority_boost += 1.5 * min(burst_storm, queue_high)
        priority_boost -= 0.5 * queue_low
        priority_boost = self._clamp(priority_boost, 0.5, 3.0)

        new_max_signals = int(current_max_signals_per_tick * throughput_factor)
        new_max_queue = int(current_max_queue_size * queue_factor)

        return {
            "max_signals_per_tick": float(
                max(self.min_signals_per_tick, min(self.max_signals_per_tick, new_max_signals))
            ),
            "max_queue_size": float(max(self.min_queue_size, min(self.max_queue_size, new_max_queue))),
            "priority_boost": priority_boost,
        }


class DeterministicSignalBus(CollectiveSignalBus):
    """Deterministic, FIFO, non-reentrant signal bus with per-tick batching."""

    def __init__(
        self,
        *,
        max_signals_per_tick: int = 10_000,
        max_queue_size: int = 100_000,
    ) -> None:
        """Initialize deterministic bus with bounded per-tick processing.

        Args:
            max_signals_per_tick: Maximum signals processed in a single `process_tick()` call.
                - 1_000: low-latency, small meshes (<100 agents)
                - 10_000: default, medium meshes (100-1000 agents)
                - 100_000: high-throughput, large meshes (1000+ agents)
            max_queue_size: Hard queue bound for pending signals. New signals above this limit
                are dropped and counted in `metrics.total_dropped`.

        Note:
            Signals over the per-tick limit remain queued for subsequent ticks.
            Monitor `metrics.max_pending_seen` and pending queue size to tune capacity.
        """
        super().__init__()
        self._pending: deque[tuple[str, InternalSignal, dict[str, str]]] = deque()
        self._processing: bool = False
        self._lock = Lock()
        self.max_signals_per_tick = max_signals_per_tick
        self.max_queue_size = max_queue_size
        self.priority_boost = 1.0
        self.regulator = FuzzyLoadRegulator(
            min_signals_per_tick=max(100, max_signals_per_tick // 10),
            max_signals_per_tick=max_signals_per_tick * 10,
            min_queue_size=max(1000, max_queue_size // 10),
            max_queue_size=max_queue_size * 10,
        )
        self.metrics = SignalBusMetrics()

    def _apply_regulator(self) -> None:
        if HAS_RUST_FUZZY and rust_compute_adjustments and RustPySignalMetrics and RustPyBusConfig:
            try:
                rust_metrics = RustPySignalMetrics(
                    queue_size=self.metrics.queue_size,
                    avg_batch_size=float(self.metrics.avgbatchsize),
                    queue_peak_per_tick=self.metrics.queuepeakper_tick,
                    total_dropped=self.metrics.total_dropped,
                    total_emitted=max(1, self.metrics.total_emitted),
                )
                rust_config = RustPyBusConfig(
                    max_signals_per_tick=max(1, self.max_signals_per_tick),
                    max_queue_size=max(1, self.max_queue_size),
                    priority_boost=float(self.priority_boost),
                )
                rust_adjustments = rust_compute_adjustments(rust_metrics, rust_config)
                self.max_signals_per_tick = int(rust_adjustments.max_signals_per_tick)
                self.max_queue_size = int(rust_adjustments.max_queue_size)
                self.priority_boost = float(rust_adjustments.priority_boost)
                return
            except Exception:
                logger.exception("Falling back to Python fuzzy regulator due to Rust compute error")

        adjustments = self.regulator.compute_adjustments(
            self.metrics,
            current_max_signals_per_tick=self.max_signals_per_tick,
            current_max_queue_size=self.max_queue_size,
        )
        self.max_signals_per_tick = int(adjustments["max_signals_per_tick"])
        self.max_queue_size = int(adjustments["max_queue_size"])
        self.priority_boost = adjustments["priority_boost"]

    def _enqueue(self, mode: str, signal: InternalSignal, kwargs: dict[str, str]) -> None:
        with self._lock:
            pending_size = len(self._pending)
            if pending_size >= self.max_queue_size:
                self.metrics.total_dropped += 1
                return
            if pending_size >= int(self.max_queue_size * 0.98):
                logger.critical(
                    "DeterministicSignalBus queue critically near capacity: %s/%s",
                    pending_size,
                    self.max_queue_size,
                )
            elif pending_size >= int(self.max_queue_size * 0.9):
                logger.warning(
                    "DeterministicSignalBus queue near capacity: %s/%s",
                    pending_size,
                    self.max_queue_size,
                )
            self.metrics.total_emitted += 1
            self._pending.append((mode, signal, kwargs))
            self.metrics.queue_size = len(self._pending)
            self.metrics.max_pending_seen = max(self.metrics.max_pending_seen, self.metrics.queue_size)

    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    def emit_local(self, signal: InternalSignal, *, target_agent_id: str) -> None:
        self._enqueue("local", signal, {"target_agent_id": target_agent_id})

    def emit_group(self, signal: InternalSignal, *, group_id: str) -> None:
        self._enqueue("group", signal, {"group_id": group_id})

    def emit_broadcast(self, signal: InternalSignal) -> None:
        self._enqueue("broadcast", signal, {})

    def emit(self, signal: InternalSignal) -> None:
        self._enqueue("broadcast", signal, {})

    def process_tick(self) -> list[InternalSignal]:
        if not self._pending:
            self._apply_regulator()
            return []

        dropped_before_tick = 0
        with self._lock:
            if self._processing:
                return []
            self._processing = True
            dropped_before_tick = self.metrics.total_dropped
            self.metrics.queuepeakper_tick = max(self.metrics.queuepeakper_tick, len(self._pending))
            batch = list(islice(self._pending, self.max_signals_per_tick))
            for _ in range(len(batch)):
                self._pending.popleft()
            self.metrics.queue_size = len(self._pending)

        processed = [signal for _, signal, _ in batch]
        try:
            for mode, signal, kwargs in batch:
                if mode == "local":
                    super().emit_local(signal, target_agent_id=kwargs["target_agent_id"])
                elif mode == "group":
                    super().emit_group(signal, group_id=kwargs["group_id"])
                else:
                    super().emit_broadcast(signal)
        finally:
            with self._lock:
                if processed:
                    self.metrics.avgbatchsize = (
                        self.metrics.avgbatchsize * self.metrics.processed_ticks + len(processed)
                    ) / (self.metrics.processed_ticks + 1)
                    self.metrics.processed_ticks += 1
                self.metrics.total_processed += len(processed)
                if self.metrics.total_dropped > dropped_before_tick:
                    self.metrics.tickswithdropped_signals += 1
                self._processing = False

            self._apply_regulator()

        return processed
