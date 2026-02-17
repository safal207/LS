import time

import pytest

from modules.web4_runtime.governance import AdaptiveGovernor
from modules.web4_runtime.metrics import MetricsCollector
from modules.web4_runtime.rtt import RttConfig, RttSession
from modules.web4_runtime.transport import TransportFailover


def test_priority_queue_heapq_ordering_and_insert_budget() -> None:
    session = RttSession[str](config=RttConfig(max_queue=10_000, enable_priority_queue=True))

    start = time.perf_counter_ns()
    for i in range(10_000):
        session.send(f"msg-{i}", priority=i % 10)
    insert_time = time.perf_counter_ns() - start

    avg_insert_time = insert_time / 10_000
    assert avg_insert_time < 200_000

    first = [session.receive() for _ in range(100)]
    parsed = [int(item.rsplit("-", 1)[1]) % 10 for item in first if item is not None]
    assert parsed
    assert parsed == sorted(parsed, reverse=True)


def test_welford_volatility_computation() -> None:
    governor = AdaptiveGovernor()

    start = time.perf_counter_ns()
    for i in range(2000):
        _ = governor.compute_adaptive_alpha(1000.0 + (i % 100))
    elapsed = time.perf_counter_ns() - start

    assert elapsed / 2000 < 100_000
    assert governor.alpha_min <= governor.alpha <= governor.alpha_max


def test_failover_recovery_automatic() -> None:
    class MockTransport:
        transport_type = "mock"

        def __init__(self, fail_after: int = 0):
            self._fail_count = 0
            self._fail_after = fail_after
            self.connected = False

        def connect(self) -> None:
            self.connected = True

        def disconnect(self) -> None:
            self.connected = False

        def send(self, message: str) -> None:
            self._fail_count += 1
            if self._fail_count <= self._fail_after:
                raise RuntimeError("Transport error")

        def receive(self) -> None:
            return None

        def pending(self) -> int:
            return 0

        def stats(self) -> object:
            return {}

        def heartbeat(self) -> None:
            pass

        def check_heartbeat_timeout(self) -> bool:
            return False

        def health_check(self) -> bool:
            return self.connected and self._fail_count >= self._fail_after

    primary = MockTransport(fail_after=3)
    backup = MockTransport()

    failover = TransportFailover(primary, backup, failover_threshold=3, recovery_success_threshold=3, recovery_check_interval_s=0)
    failover.connect()

    for _ in range(3):
        with pytest.raises(RuntimeError):
            failover.send("msg")

    assert failover._using_backup is True

    for _ in range(3):
        failover.send("msg")

    assert failover._using_backup is False


def test_metrics_collector_budget_violations() -> None:
    collector = MetricsCollector()

    collector.record_volatility_computation(500)
    collector.record_priority_queue_insert(1000)
    assert collector.check_budgets() == []

    collector.record_volatility_computation(6000)
    violations = collector.check_budgets()
    assert len(violations) == 1
    assert violations[0]["severity"] == "critical"
    assert violations[0]["metric"] == "volatility_computation_time_ns"


def test_priority_queue_p99_wait_time() -> None:
    collector = MetricsCollector()

    for i in range(1000):
        collector.record_priority_wait_time(float(i))

    metrics = collector.get_metrics()
    assert 980 <= metrics.priority_queue_wait_time_p99_ms <= 999


def test_priority_queue_overflow_with_none_priority() -> None:
    session = RttSession[str](
        config=RttConfig(max_queue=1, enable_priority_queue=True, backpressure_policy="dropnewest")
    )

    session.send("first")
    session.send("second", priority=None)

    assert session.receive() == "first"
    assert session.receive() is None
    assert session.stats.dropped_newest == 1
