from __future__ import annotations

import asyncio
import gc
from dataclasses import dataclass, field
from random import Random
from threading import Thread
from time import perf_counter, sleep
from typing import Any, Literal

from .async_rtt import AsyncRttSession
from .flow import GlobalFlowController
from .rtt import BackpressureError, DisconnectedError, RttConfig, RttSession

Phase = Literal["phase1", "phase2", "phase3", "phase4"]
Mode = Literal["sync", "async", "both"]


@dataclass(frozen=True)
class LoadTestConfig:
    phase: Phase = "phase1"
    mode: Mode = "both"
    sessions: int = 10
    messages_per_session: int = 200
    max_queue: int = 64
    total_limit: int = 512
    per_session_limit: int = 64
    block_timeout_s: float = 0.8
    random_seed: int = 42
    chaos_disconnect_rate: float = 0.08
    burst_probability: float = 0.12
    burst_size: int = 16
    soak_duration_s: float = 30.0
    target_messages_per_s: int = 200
    gc_pressure: bool = False

    def __post_init__(self) -> None:
        if self.sessions < 1:
            raise ValueError("sessions must be >= 1")
        if self.messages_per_session < 1:
            raise ValueError("messages_per_session must be >= 1")
        if self.max_queue < 1:
            raise ValueError("max_queue must be >= 1")
        if self.total_limit < 1:
            raise ValueError("total_limit must be >= 1")
        if self.per_session_limit < 1:
            raise ValueError("per_session_limit must be >= 1")
        if self.block_timeout_s <= 0:
            raise ValueError("block_timeout_s must be > 0")
        if not 0.0 <= self.chaos_disconnect_rate <= 1.0:
            raise ValueError("chaos_disconnect_rate must be between 0.0 and 1.0")
        if not 0.0 <= self.burst_probability <= 1.0:
            raise ValueError("burst_probability must be between 0.0 and 1.0")
        if self.burst_size < 1:
            raise ValueError("burst_size must be >= 1")
        if self.soak_duration_s <= 0:
            raise ValueError("soak_duration_s must be > 0")
        if self.target_messages_per_s < 1:
            raise ValueError("target_messages_per_s must be >= 1")


@dataclass
class _ScenarioResult:
    scenario: str
    phase: Phase
    mode: Literal["sync", "async"]
    total_limit: int
    attempted: int
    enqueued: int
    received: int
    max_total_pending: int
    max_session_pending: int
    duration_s: float
    wakeup_latencies_ms: list[float]
    errors: list[str]
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "phase": self.phase,
            "mode": self.mode,
            "passed": self.passed,
            "total_limit": self.total_limit,
            "attempted": self.attempted,
            "enqueued": self.enqueued,
            "received": self.received,
            "max_total_pending": self.max_total_pending,
            "max_session_pending": self.max_session_pending,
            "duration_s": round(self.duration_s, 6),
            "wakeup_latency_ms": {
                "count": len(self.wakeup_latencies_ms),
                "p50": _percentile(self.wakeup_latencies_ms, 50.0),
                "p95": _percentile(self.wakeup_latencies_ms, 95.0),
                "p99": _percentile(self.wakeup_latencies_ms, 99.0),
            },
            "extra": self.extra,
            "errors": self.errors,
        }


def run_load_test(config: LoadTestConfig) -> dict[str, Any]:
    results: list[_ScenarioResult] = []
    if config.mode in ("sync", "both"):
        results.append(_run_sync(config))
    if config.mode in ("async", "both"):
        results.append(_run_async(config))

    return {
        "phase": config.phase,
        "mode": config.mode,
        "overall_passed": all(item.passed for item in results),
        "results": [item.to_dict() for item in results],
    }


def _run_sync(config: LoadTestConfig) -> _ScenarioResult:
    if config.phase == "phase1":
        return _run_phase1_sync(config)
    if config.phase == "phase2":
        return _run_phase2_sync(config)
    if config.phase == "phase3":
        return _run_phase3_sync(config)
    return _run_phase4_sync(config)


def _run_async(config: LoadTestConfig) -> _ScenarioResult:
    if config.phase == "phase1":
        return _run_phase1_async(config)
    if config.phase == "phase2":
        return _run_phase2_async(config)
    if config.phase == "phase3":
        return _run_phase3_async(config)
    return _run_phase4_async(config)


def _append_error(errors: list[str], message: str) -> None:
    if len(errors) < 40:
        errors.append(message)


def _run_phase1_sync(config: LoadTestConfig) -> _ScenarioResult:
    started_at = perf_counter()
    errors: list[str] = []
    wakeup_latencies_ms: list[float] = []

    flow: GlobalFlowController[RttSession[str]] = GlobalFlowController(total_limit=1, per_session_limit=1)
    owner = RttSession[str](
        config=RttConfig(max_queue=2, backpressure_policy="error"),
        flow_controller=flow,
    )
    blocked = RttSession[str](
        config=RttConfig(max_queue=2, backpressure_policy="block", block_timeout_s=config.block_timeout_s),
        flow_controller=flow,
    )

    max_total_pending = 0
    max_session_pending = 0

    def observe() -> None:
        nonlocal max_total_pending, max_session_pending
        total_pending = flow.total_pending
        local_pending_sum = owner.pending + blocked.pending
        max_total_pending = max(max_total_pending, total_pending)
        max_session_pending = max(max_session_pending, owner.pending, blocked.pending)
        if total_pending != local_pending_sum:
            errors.append(
                f"sync-phase1 invariant failed: total_pending={total_pending} sum_pending={local_pending_sum}"
            )
        if total_pending > flow.total_limit:
            errors.append(
                f"sync-phase1 invariant failed: total_pending {total_pending} exceeds total_limit {flow.total_limit}"
            )

    owner.send("seed")
    observe()

    worker_error: list[str] = []

    def sender() -> None:
        sender_started_at = perf_counter()
        try:
            blocked.send("blocked")
            wakeup_latencies_ms.append((perf_counter() - sender_started_at) * 1000.0)
        except Exception as exc:  # pragma: no cover - exercised in negative paths only
            worker_error.append(repr(exc))

    worker = Thread(target=sender, daemon=True)
    worker.start()
    sleep(0.03)
    observe()

    received = owner.receive()
    if received != "seed":
        errors.append(f"sync-phase1 expected to receive 'seed', got {received!r}")
    observe()

    worker.join(timeout=1.0)
    if worker.is_alive():
        errors.append("sync-phase1 blocked sender did not wake within 1.0s")
    if worker_error:
        errors.extend(worker_error)

    received = blocked.receive()
    if received != "blocked":
        errors.append(f"sync-phase1 expected to receive 'blocked', got {received!r}")
    observe()

    return _ScenarioResult(
        scenario="phase1_baseline_correctness",
        phase=config.phase,
        mode="sync",
        total_limit=flow.total_limit,
        attempted=owner.stats.attempted + blocked.stats.attempted,
        enqueued=owner.stats.enqueued + blocked.stats.enqueued,
        received=2,
        max_total_pending=max_total_pending,
        max_session_pending=max_session_pending,
        duration_s=perf_counter() - started_at,
        wakeup_latencies_ms=wakeup_latencies_ms,
        errors=errors,
    )


def _run_phase2_sync(config: LoadTestConfig) -> _ScenarioResult:
    started_at = perf_counter()
    errors: list[str] = []
    rng = Random(config.random_seed)
    flow: GlobalFlowController[RttSession[str]] = GlobalFlowController(
        total_limit=config.total_limit,
        per_session_limit=config.per_session_limit,
    )
    sessions = [
        RttSession[str](
            config=RttConfig(
                max_queue=config.max_queue,
                backpressure_policy="dropoldest",
                enable_priority_queue=True,
            ),
            flow_controller=flow,
        )
        for _ in range(config.sessions)
    ]

    max_total_pending = 0
    max_session_pending = 0
    received_count = 0

    def observe() -> None:
        nonlocal max_total_pending, max_session_pending
        total_pending = flow.total_pending
        local_pending_sum = sum(session.pending for session in sessions)
        max_total_pending = max(max_total_pending, total_pending)
        max_session_pending = max(max_session_pending, *(session.pending for session in sessions))
        if total_pending != local_pending_sum:
            errors.append(
                f"sync-phase2 invariant failed: total_pending={total_pending} sum_pending={local_pending_sum}"
            )
        if total_pending > flow.total_limit:
            errors.append(
                f"sync-phase2 invariant failed: total_pending {total_pending} exceeds total_limit {flow.total_limit}"
            )

    attempted = 0
    steps = config.sessions * config.messages_per_session
    for step in range(steps):
        session = sessions[rng.randrange(config.sessions)]
        priority = rng.randint(1, 9) if rng.random() < 0.5 else None
        session.send(f"msg-{step}", priority=priority)
        attempted += 1

        if step % 3 == 0:
            sink = sessions[rng.randrange(config.sessions)]
            item = sink.receive()
            if item is not None:
                received_count += 1
        observe()

    for session in sessions:
        while True:
            item = session.receive()
            if item is None:
                break
            received_count += 1
        observe()

    enqueued = sum(session.stats.enqueued for session in sessions)
    return _ScenarioResult(
        scenario="phase2_stress_sanity",
        phase=config.phase,
        mode="sync",
        total_limit=flow.total_limit,
        attempted=attempted,
        enqueued=enqueued,
        received=received_count,
        max_total_pending=max_total_pending,
        max_session_pending=max_session_pending,
        duration_s=perf_counter() - started_at,
        wakeup_latencies_ms=[],
        errors=errors,
    )


def _run_phase3_sync(config: LoadTestConfig) -> _ScenarioResult:
    started_at = perf_counter()
    errors: list[str] = []
    rng = Random(config.random_seed)

    flow = GlobalFlowController(total_limit=config.total_limit, per_session_limit=config.per_session_limit)
    sessions = [
        RttSession[str](
            config=RttConfig(
                max_queue=config.max_queue,
                backpressure_policy="dropoldest",
                block_timeout_s=config.block_timeout_s,
                enable_priority_queue=True,
            ),
            flow_controller=flow,
        )
        for _ in range(config.sessions)
    ]

    max_total_pending = 0
    max_session_pending = 0
    received_count = 0
    disconnect_events = 0
    reconnect_events = 0
    burst_rounds = 0

    def observe() -> None:
        nonlocal max_total_pending, max_session_pending
        total_pending = flow.total_pending
        local_pending_sum = sum(session.pending for session in sessions)
        max_total_pending = max(max_total_pending, total_pending)
        local_max_pending = max((session.pending for session in sessions), default=0)
        max_session_pending = max(max_session_pending, local_max_pending)
        if total_pending != local_pending_sum:
            _append_error(
                errors,
                f"sync-phase3 invariant failed: total_pending={total_pending} sum_pending={local_pending_sum}",
            )
        if total_pending > flow.total_limit:
            _append_error(
                errors,
                f"sync-phase3 invariant failed: total_pending {total_pending} exceeds total_limit {flow.total_limit}",
            )
        if local_max_pending > config.max_queue:
            _append_error(errors, "sync-phase3 invariant failed: session.pending exceeded max_queue")

    steps = config.sessions * config.messages_per_session
    for step in range(steps):
        if rng.random() < config.chaos_disconnect_rate:
            toggled = sessions[rng.randrange(config.sessions)]
            if toggled.connected:
                toggled.disconnect("chaos")
                disconnect_events += 1
            else:
                toggled.reconnect()
                reconnect_events += 1

        burst = config.burst_size if rng.random() < config.burst_probability else 1
        if burst > 1:
            burst_rounds += 1
        for burst_index in range(burst):
            session = sessions[rng.randrange(config.sessions)]
            if not session.connected:
                if rng.random() < 0.6:
                    session.reconnect()
                    reconnect_events += 1
                else:
                    continue

            priority = rng.randint(1, 9) if rng.random() < 0.5 else None
            try:
                session.send(f"chaos-{step}-{burst_index}", priority=priority)
            except (BackpressureError, DisconnectedError) as exc:
                _append_error(errors, f"sync-phase3 unexpected send failure: {exc!r}")
                continue

            if rng.random() < 0.45:
                sink = sessions[rng.randrange(config.sessions)]
                if sink.connected:
                    item = sink.receive()
                    if item is not None:
                        received_count += 1

        if config.gc_pressure and step % 20 == 0:
            gc.collect()
        observe()

    for session in sessions:
        if not session.connected:
            session.reconnect()
            reconnect_events += 1
        while True:
            item = session.receive()
            if item is None:
                break
            received_count += 1
        observe()

    return _ScenarioResult(
        scenario="phase3_chaos_validation",
        phase=config.phase,
        mode="sync",
        total_limit=flow.total_limit,
        attempted=sum(session.stats.attempted for session in sessions),
        enqueued=sum(session.stats.enqueued for session in sessions),
        received=received_count,
        max_total_pending=max_total_pending,
        max_session_pending=max_session_pending,
        duration_s=perf_counter() - started_at,
        wakeup_latencies_ms=[],
        errors=errors,
        extra={
            "disconnect_events": disconnect_events,
            "reconnect_events": reconnect_events,
            "burst_rounds": burst_rounds,
        },
    )


def _run_phase4_sync(config: LoadTestConfig) -> _ScenarioResult:
    started_at = perf_counter()
    errors: list[str] = []
    rng = Random(config.random_seed)
    flow = GlobalFlowController(total_limit=config.total_limit, per_session_limit=config.per_session_limit)
    sessions = [
        RttSession[str](
            config=RttConfig(
                max_queue=config.max_queue,
                backpressure_policy="dropoldest",
                block_timeout_s=config.block_timeout_s,
                enable_priority_queue=True,
            ),
            flow_controller=flow,
        )
        for _ in range(config.sessions)
    ]

    max_total_pending = 0
    max_session_pending = 0
    received_count = 0
    duration_target = max(0.05, config.soak_duration_s)
    target_interval = 1.0 / max(1, config.target_messages_per_s)
    next_emit = perf_counter()
    steps = 0

    def observe() -> None:
        nonlocal max_total_pending, max_session_pending
        total_pending = flow.total_pending
        local_pending_sum = sum(session.pending for session in sessions)
        max_total_pending = max(max_total_pending, total_pending)
        local_max_pending = max((session.pending for session in sessions), default=0)
        max_session_pending = max(max_session_pending, local_max_pending)
        if total_pending != local_pending_sum:
            _append_error(
                errors,
                f"sync-phase4 invariant failed: total_pending={total_pending} sum_pending={local_pending_sum}",
            )
        if total_pending > flow.total_limit:
            _append_error(
                errors,
                f"sync-phase4 invariant failed: total_pending {total_pending} exceeds total_limit {flow.total_limit}",
            )
        if local_max_pending > config.max_queue:
            _append_error(errors, "sync-phase4 invariant failed: session.pending exceeded max_queue")

    while perf_counter() - started_at < duration_target:
        if steps % max(2, config.sessions) == 0 and rng.random() < (config.chaos_disconnect_rate * 0.5):
            toggled = sessions[rng.randrange(config.sessions)]
            if toggled.connected:
                toggled.disconnect("soak")
            else:
                toggled.reconnect()

        burst = config.burst_size if rng.random() < (config.burst_probability * 0.35) else 1
        for burst_index in range(burst):
            session = sessions[rng.randrange(config.sessions)]
            if not session.connected:
                if rng.random() < 0.6:
                    session.reconnect()
                else:
                    continue
            priority = rng.randint(1, 9) if rng.random() < 0.5 else None
            try:
                session.send(f"soak-{steps}-{burst_index}", priority=priority)
            except (BackpressureError, DisconnectedError) as exc:
                _append_error(errors, f"sync-phase4 unexpected send failure: {exc!r}")
                continue

            if rng.random() < 0.55:
                sink = sessions[rng.randrange(config.sessions)]
                if sink.connected:
                    item = sink.receive()
                    if item is not None:
                        received_count += 1

        if config.gc_pressure and steps % 50 == 0:
            gc.collect()
        observe()

        steps += 1
        next_emit += target_interval
        delay = next_emit - perf_counter()
        if delay > 0:
            sleep(min(delay, 0.01))
        else:
            next_emit = perf_counter()

    for session in sessions:
        if not session.connected:
            session.reconnect()
        while True:
            item = session.receive()
            if item is None:
                break
            received_count += 1
        observe()

    return _ScenarioResult(
        scenario="phase4_soak_stability",
        phase=config.phase,
        mode="sync",
        total_limit=flow.total_limit,
        attempted=sum(session.stats.attempted for session in sessions),
        enqueued=sum(session.stats.enqueued for session in sessions),
        received=received_count,
        max_total_pending=max_total_pending,
        max_session_pending=max_session_pending,
        duration_s=perf_counter() - started_at,
        wakeup_latencies_ms=[],
        errors=errors,
        extra={
            "target_messages_per_s": config.target_messages_per_s,
            "duration_target_s": duration_target,
            "loop_steps": steps,
        },
    )


def _run_phase1_async(config: LoadTestConfig) -> _ScenarioResult:
    started_at = perf_counter()
    errors: list[str] = []
    wakeup_latencies_ms: list[float] = []

    stats: dict[str, int] = {"attempted": 0, "enqueued": 0, "received": 0}
    max_total_pending = 0
    max_session_pending = 0

    async def scenario() -> None:
        nonlocal max_total_pending, max_session_pending
        flow: GlobalFlowController[AsyncRttSession[str]] = GlobalFlowController(total_limit=1, per_session_limit=1)
        owner = AsyncRttSession[str](
            config=RttConfig(max_queue=2, backpressure_policy="error"),
            flow_controller=flow,
        )
        blocked = AsyncRttSession[str](
            config=RttConfig(max_queue=2, backpressure_policy="block", block_timeout_s=config.block_timeout_s),
            flow_controller=flow,
        )

        def observe() -> None:
            nonlocal max_total_pending, max_session_pending
            total_pending = flow.total_pending
            local_pending_sum = owner.pending + blocked.pending
            max_total_pending = max(max_total_pending, total_pending)
            max_session_pending = max(max_session_pending, owner.pending, blocked.pending)
            if total_pending != local_pending_sum:
                errors.append(
                    f"async-phase1 invariant failed: total_pending={total_pending} sum_pending={local_pending_sum}"
                )
            if total_pending > flow.total_limit:
                errors.append(
                    f"async-phase1 invariant failed: total_pending {total_pending} exceeds total_limit {flow.total_limit}"
                )

        await owner.send_async("seed")
        observe()

        send_started_at = perf_counter()
        producer = asyncio.create_task(blocked.send_async("blocked"))
        await asyncio.sleep(0.03)
        observe()

        received = await owner.receive_async()
        if received != "seed":
            errors.append(f"async-phase1 expected to receive 'seed', got {received!r}")
        observe()

        await producer
        wakeup_latencies_ms.append((perf_counter() - send_started_at) * 1000.0)

        received = await blocked.receive_async()
        if received != "blocked":
            errors.append(f"async-phase1 expected to receive 'blocked', got {received!r}")
        observe()

        stats["attempted"] = owner.stats.attempted + blocked.stats.attempted
        stats["enqueued"] = owner.stats.enqueued + blocked.stats.enqueued
        stats["received"] = 2

    asyncio.run(scenario())
    return _ScenarioResult(
        scenario="phase1_baseline_correctness",
        phase=config.phase,
        mode="async",
        total_limit=1,
        attempted=stats["attempted"],
        enqueued=stats["enqueued"],
        received=stats["received"],
        max_total_pending=max_total_pending,
        max_session_pending=max_session_pending,
        duration_s=perf_counter() - started_at,
        wakeup_latencies_ms=wakeup_latencies_ms,
        errors=errors,
    )


def _run_phase2_async(config: LoadTestConfig) -> _ScenarioResult:
    started_at = perf_counter()
    errors: list[str] = []
    rng = Random(config.random_seed)

    stats: dict[str, int] = {"attempted": 0, "enqueued": 0, "received": 0}
    max_total_pending = 0
    max_session_pending = 0

    async def scenario() -> None:
        nonlocal max_total_pending, max_session_pending
        flow: GlobalFlowController[AsyncRttSession[str]] = GlobalFlowController(
            total_limit=config.total_limit,
            per_session_limit=config.per_session_limit,
        )
        sessions = [
            AsyncRttSession[str](
                config=RttConfig(
                    max_queue=config.max_queue,
                    backpressure_policy="dropoldest",
                    enable_priority_queue=True,
                ),
                flow_controller=flow,
            )
            for _ in range(config.sessions)
        ]

        def observe() -> None:
            nonlocal max_total_pending, max_session_pending
            total_pending = flow.total_pending
            local_pending_sum = sum(session.pending for session in sessions)
            max_total_pending = max(max_total_pending, total_pending)
            max_session_pending = max(max_session_pending, *(session.pending for session in sessions))
            if total_pending != local_pending_sum:
                errors.append(
                    f"async-phase2 invariant failed: total_pending={total_pending} sum_pending={local_pending_sum}"
                )
            if total_pending > flow.total_limit:
                errors.append(
                    f"async-phase2 invariant failed: total_pending {total_pending} exceeds total_limit {flow.total_limit}"
                )

        attempted = 0
        received = 0
        steps = config.sessions * config.messages_per_session
        for step in range(steps):
            session = sessions[rng.randrange(config.sessions)]
            priority = rng.randint(1, 9) if rng.random() < 0.5 else None
            await session.send_async(f"msg-{step}", priority=priority)
            attempted += 1

            if step % 3 == 0:
                sink = sessions[rng.randrange(config.sessions)]
                item = await sink.receive_async()
                if item is not None:
                    received += 1
            observe()

            if step % 25 == 0:
                await asyncio.sleep(0)

        for session in sessions:
            while True:
                item = await session.receive_async()
                if item is None:
                    break
                received += 1
            observe()

        stats["attempted"] = attempted
        stats["enqueued"] = sum(session.stats.enqueued for session in sessions)
        stats["received"] = received

    asyncio.run(scenario())
    return _ScenarioResult(
        scenario="phase2_stress_sanity",
        phase=config.phase,
        mode="async",
        total_limit=config.total_limit,
        attempted=stats["attempted"],
        enqueued=stats["enqueued"],
        received=stats["received"],
        max_total_pending=max_total_pending,
        max_session_pending=max_session_pending,
        duration_s=perf_counter() - started_at,
        wakeup_latencies_ms=[],
        errors=errors,
    )


def _run_phase3_async(config: LoadTestConfig) -> _ScenarioResult:
    started_at = perf_counter()
    errors: list[str] = []
    rng = Random(config.random_seed)

    stats: dict[str, int] = {"attempted": 0, "enqueued": 0, "received": 0}
    meta: dict[str, int] = {"disconnect_events": 0, "reconnect_events": 0, "burst_rounds": 0}
    max_total_pending = 0
    max_session_pending = 0

    async def scenario() -> None:
        nonlocal max_total_pending, max_session_pending
        flow = GlobalFlowController(total_limit=config.total_limit, per_session_limit=config.per_session_limit)
        sessions = [
            AsyncRttSession[str](
                config=RttConfig(
                    max_queue=config.max_queue,
                    backpressure_policy="dropoldest",
                    block_timeout_s=config.block_timeout_s,
                    enable_priority_queue=True,
                ),
                flow_controller=flow,
            )
            for _ in range(config.sessions)
        ]

        def observe() -> None:
            nonlocal max_total_pending, max_session_pending
            total_pending = flow.total_pending
            local_pending_sum = sum(session.pending for session in sessions)
            max_total_pending = max(max_total_pending, total_pending)
            local_max_pending = max((session.pending for session in sessions), default=0)
            max_session_pending = max(max_session_pending, local_max_pending)
            if total_pending != local_pending_sum:
                _append_error(
                    errors,
                    f"async-phase3 invariant failed: total_pending={total_pending} sum_pending={local_pending_sum}",
                )
            if total_pending > flow.total_limit:
                _append_error(
                    errors,
                    f"async-phase3 invariant failed: total_pending {total_pending} exceeds total_limit {flow.total_limit}",
                )
            if local_max_pending > config.max_queue:
                _append_error(errors, "async-phase3 invariant failed: session.pending exceeded max_queue")

        steps = config.sessions * config.messages_per_session
        attempted = 0
        received = 0
        for step in range(steps):
            if rng.random() < config.chaos_disconnect_rate:
                toggled = sessions[rng.randrange(config.sessions)]
                if toggled.connected:
                    await toggled.disconnect()
                    meta["disconnect_events"] += 1
                else:
                    await toggled.reconnect()
                    meta["reconnect_events"] += 1

            burst = config.burst_size if rng.random() < config.burst_probability else 1
            if burst > 1:
                meta["burst_rounds"] += 1

            for burst_index in range(burst):
                session = sessions[rng.randrange(config.sessions)]
                if not session.connected:
                    if rng.random() < 0.6:
                        await session.reconnect()
                        meta["reconnect_events"] += 1
                    else:
                        continue

                priority = rng.randint(1, 9) if rng.random() < 0.5 else None
                attempted += 1
                try:
                    await session.send_async(f"chaos-{step}-{burst_index}", priority=priority)
                except (BackpressureError, DisconnectedError) as exc:
                    _append_error(errors, f"async-phase3 unexpected send failure: {exc!r}")
                    continue

                if rng.random() < 0.45:
                    sink = sessions[rng.randrange(config.sessions)]
                    if sink.connected:
                        item = await sink.receive_async()
                        if item is not None:
                            received += 1
            if config.gc_pressure and step % 20 == 0:
                gc.collect()
            observe()
            if step % 20 == 0:
                await asyncio.sleep(0)

        for session in sessions:
            if not session.connected:
                await session.reconnect()
                meta["reconnect_events"] += 1
            while True:
                item = await session.receive_async()
                if item is None:
                    break
                received += 1
            observe()

        stats["attempted"] = attempted
        stats["enqueued"] = sum(session.stats.enqueued for session in sessions)
        stats["received"] = received

    asyncio.run(scenario())
    return _ScenarioResult(
        scenario="phase3_chaos_validation",
        phase=config.phase,
        mode="async",
        total_limit=config.total_limit,
        attempted=stats["attempted"],
        enqueued=stats["enqueued"],
        received=stats["received"],
        max_total_pending=max_total_pending,
        max_session_pending=max_session_pending,
        duration_s=perf_counter() - started_at,
        wakeup_latencies_ms=[],
        errors=errors,
        extra=meta,
    )


def _run_phase4_async(config: LoadTestConfig) -> _ScenarioResult:
    started_at = perf_counter()
    errors: list[str] = []
    rng = Random(config.random_seed)

    stats: dict[str, int] = {"attempted": 0, "enqueued": 0, "received": 0, "loop_steps": 0}
    max_total_pending = 0
    max_session_pending = 0
    duration_target = max(0.05, config.soak_duration_s)
    target_interval = 1.0 / max(1, config.target_messages_per_s)

    async def scenario() -> None:
        nonlocal max_total_pending, max_session_pending
        flow = GlobalFlowController(total_limit=config.total_limit, per_session_limit=config.per_session_limit)
        sessions = [
            AsyncRttSession[str](
                config=RttConfig(
                    max_queue=config.max_queue,
                    backpressure_policy="dropoldest",
                    block_timeout_s=config.block_timeout_s,
                    enable_priority_queue=True,
                ),
                flow_controller=flow,
            )
            for _ in range(config.sessions)
        ]

        def observe() -> None:
            nonlocal max_total_pending, max_session_pending
            total_pending = flow.total_pending
            local_pending_sum = sum(session.pending for session in sessions)
            max_total_pending = max(max_total_pending, total_pending)
            local_max_pending = max((session.pending for session in sessions), default=0)
            max_session_pending = max(max_session_pending, local_max_pending)
            if total_pending != local_pending_sum:
                _append_error(
                    errors,
                    f"async-phase4 invariant failed: total_pending={total_pending} sum_pending={local_pending_sum}",
                )
            if total_pending > flow.total_limit:
                _append_error(
                    errors,
                    f"async-phase4 invariant failed: total_pending {total_pending} exceeds total_limit {flow.total_limit}",
                )
            if local_max_pending > config.max_queue:
                _append_error(errors, "async-phase4 invariant failed: session.pending exceeded max_queue")

        attempted = 0
        received = 0
        loop = asyncio.get_running_loop()
        phase_started = loop.time()
        next_emit = phase_started
        steps = 0

        while loop.time() - phase_started < duration_target:
            if steps % max(2, config.sessions) == 0 and rng.random() < (config.chaos_disconnect_rate * 0.5):
                toggled = sessions[rng.randrange(config.sessions)]
                if toggled.connected:
                    await toggled.disconnect()
                else:
                    await toggled.reconnect()

            burst = config.burst_size if rng.random() < (config.burst_probability * 0.35) else 1
            for burst_index in range(burst):
                session = sessions[rng.randrange(config.sessions)]
                if not session.connected:
                    if rng.random() < 0.6:
                        await session.reconnect()
                    else:
                        continue
                priority = rng.randint(1, 9) if rng.random() < 0.5 else None
                attempted += 1
                try:
                    await session.send_async(f"soak-{steps}-{burst_index}", priority=priority)
                except (BackpressureError, DisconnectedError) as exc:
                    _append_error(errors, f"async-phase4 unexpected send failure: {exc!r}")
                    continue

                if rng.random() < 0.55:
                    sink = sessions[rng.randrange(config.sessions)]
                    if sink.connected:
                        item = await sink.receive_async()
                        if item is not None:
                            received += 1

            if config.gc_pressure and steps % 50 == 0:
                gc.collect()
            observe()

            steps += 1
            next_emit += target_interval
            remaining = next_emit - loop.time()
            if remaining > 0:
                await asyncio.sleep(min(remaining, 0.01))
            else:
                next_emit = loop.time()
                await asyncio.sleep(0)

        for session in sessions:
            if not session.connected:
                await session.reconnect()
            while True:
                item = await session.receive_async()
                if item is None:
                    break
                received += 1
            observe()

        stats["attempted"] = attempted
        stats["enqueued"] = sum(session.stats.enqueued for session in sessions)
        stats["received"] = received
        stats["loop_steps"] = steps

    asyncio.run(scenario())
    return _ScenarioResult(
        scenario="phase4_soak_stability",
        phase=config.phase,
        mode="async",
        total_limit=config.total_limit,
        attempted=stats["attempted"],
        enqueued=stats["enqueued"],
        received=stats["received"],
        max_total_pending=max_total_pending,
        max_session_pending=max_session_pending,
        duration_s=perf_counter() - started_at,
        wakeup_latencies_ms=[],
        errors=errors,
        extra={
            "target_messages_per_s": config.target_messages_per_s,
            "duration_target_s": duration_target,
            "loop_steps": stats["loop_steps"],
        },
    )


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return round(values[0], 3)

    ordered = sorted(values)
    rank = (len(ordered) - 1) * (percentile / 100.0)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return round(ordered[low] * (1.0 - weight) + ordered[high] * weight, 3)
