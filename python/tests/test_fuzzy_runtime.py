from __future__ import annotations

import asyncio
import random
import time

from modules.web4_runtime.async_rtt import AsyncRttSession
from modules.web4_runtime.flow import GlobalFlowController
from modules.web4_runtime.fuzzy import (
    FuzzyBackpressureConfig,
    FuzzyCoherenceConfig,
    smooth_coherence,
    tune_backpressure_limits,
)


def test_smooth_coherence_clamps_bounds() -> None:
    cfg = FuzzyCoherenceConfig(min_coherence=0.0, max_coherence=1.0)
    value = smooth_coherence(1.2, -0.5, drift=0.2, noise=0.2, config=cfg)
    assert 0.0 <= value <= 1.0


def test_smooth_coherence_reduces_jump_under_noise() -> None:
    raw_jump = abs(0.9 - 0.2)
    smoothed = smooth_coherence(0.9, 0.2, drift=0.1, noise=0.2)
    assert abs(smoothed - 0.9) < raw_jump


def test_smooth_coherence_moves_toward_measurement() -> None:
    value = smooth_coherence(0.2, 0.8, drift=0.05, noise=0.01)
    assert 0.2 < value < 0.8


def test_backpressure_limits_scale_down_on_pressure() -> None:
    per, total = tune_backpressure_limits(100, 1000, queue_pressure=0.95, drop_ratio=0.5)
    assert per < 100
    assert total < 1000


def test_backpressure_limits_scale_up_when_stable() -> None:
    cfg = FuzzyBackpressureConfig(max_factor=1.3)
    per, total = tune_backpressure_limits(100, 1000, queue_pressure=0.05, drop_ratio=0.0, config=cfg)
    assert per >= 100
    assert total >= 1000


def test_backpressure_limits_keep_total_above_per_session() -> None:
    per, total = tune_backpressure_limits(200, 150, queue_pressure=0.9, drop_ratio=0.9)
    assert total >= per


def test_global_flow_fuzzy_strategy_adapts_limits() -> None:
    flow = GlobalFlowController(total_limit=4, per_session_limit=4, strategy="fuzzy")
    s1, s2 = object(), object()
    flow.register_session(s1)
    flow.register_session(s2)

    baseline_total = flow._fuzzy_total_limit
    baseline_per_session = flow._fuzzy_per_session_limit

    for _ in range(8):
        flow.try_enqueue(s1)

    time.sleep(0.15)
    flow.can_enqueue(s2)

    assert (flow._fuzzy_total_limit, flow._fuzzy_per_session_limit) != (baseline_total, baseline_per_session)


def test_async_rtt_lce_coherence_update() -> None:
    async def scenario() -> None:
        session = AsyncRttSession[str]()
        start = session.coherence
        value = await session.update_lce_coherence(0.1, drift=0.3, noise=0.2)
        assert 0.0 <= value <= 1.0
        assert value != start

    asyncio.run(scenario())


def test_integration_global_flow_stability_under_noise() -> None:
    flow = GlobalFlowController(total_limit=50, per_session_limit=15, strategy="fuzzy")
    sessions = [object() for _ in range(8)]
    for s in sessions:
        flow.register_session(s)

    accepted = 0
    for _ in range(500):
        s = random.choice(sessions)
        if random.random() < 0.62:
            accepted += int(flow.try_enqueue(s))
        else:
            flow.on_dequeue(s)

    assert flow.total_pending >= 0
    assert flow._fuzzy_total_limit > 0
    assert accepted > 0


def test_flow_fuzzy_records_attempt_drop_ratio() -> None:
    flow = GlobalFlowController(total_limit=1, per_session_limit=1, strategy="fuzzy")
    s = object()
    flow.register_session(s)

    assert flow.try_enqueue(s) is True
    assert flow.try_enqueue(s) is False
    assert flow._attempted_recent >= 2
    assert flow._dropped_recent >= 1


def test_tune_backpressure_hysteresis_deadband() -> None:
    cfg = FuzzyBackpressureConfig(hysteresis_ratio=0.20)
    per, total = tune_backpressure_limits(100, 1000, queue_pressure=0.45, drop_ratio=0.0, config=cfg)
    assert per == 100
    assert total == 1000


def test_async_lce_coherence_updates_are_serialized(monkeypatch) -> None:
    from modules.web4_runtime import async_rtt

    def _bump(prev: float, measured: float, drift: float, noise: float) -> float:
        _ = (measured, drift, noise)
        return prev + 1.0

    monkeypatch.setattr(async_rtt, "smooth_coherence", _bump)

    async def scenario() -> None:
        session = AsyncRttSession[str]()

        async def worker() -> None:
            await session.update_lce_coherence(0.0)

        await asyncio.gather(worker(), worker())
        assert session.coherence == 3.0

    asyncio.run(scenario())
