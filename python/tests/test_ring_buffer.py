"""Unit tests for deque(maxlen=N) ring buffer behavior.

Covers boundary conditions: overflow, empty buffer, high-frequency insertions,
and verifies the patterns used in MetricsCollector and DeterministicSignalBus.
"""

from collections import deque

import pytest


class TestDequeMaxlenBehavior:
    """Core deque(maxlen=N) contract tests."""

    def test_overflow_evicts_oldest(self):
        buf = deque(maxlen=3)
        for i in range(5):
            buf.append(i)
        assert list(buf) == [2, 3, 4]
        assert len(buf) == 3

    def test_empty_buffer_iteration(self):
        buf = deque(maxlen=10)
        assert list(buf) == []
        assert len(buf) == 0
        # sum/min/max on empty should not crash with default
        assert sum(buf) == 0

    def test_high_frequency_insertions(self):
        maxlen = 100
        buf = deque(maxlen=maxlen)
        n = 100_000
        for i in range(n):
            buf.append(i)
        assert len(buf) == maxlen
        assert buf[0] == n - maxlen
        assert buf[-1] == n - 1

    def test_maxlen_one(self):
        buf = deque(maxlen=1)
        buf.append("a")
        assert list(buf) == ["a"]
        buf.append("b")
        assert list(buf) == ["b"]

    def test_appendleft_also_evicts(self):
        buf = deque(maxlen=3)
        buf.extend([1, 2, 3])
        buf.appendleft(0)
        # appendleft pushes from left, evicts from right
        assert list(buf) == [0, 1, 2]
        assert 3 not in buf

    def test_extend_beyond_maxlen(self):
        buf = deque(maxlen=3)
        buf.extend(range(10))
        assert list(buf) == [7, 8, 9]

    def test_maxlen_preserved_after_clear(self):
        buf = deque(maxlen=5)
        buf.extend(range(5))
        buf.clear()
        assert len(buf) == 0
        assert buf.maxlen == 5
        buf.extend(range(10))
        assert len(buf) == 5


class TestMetricsCollectorPattern:
    """Tests mirroring MetricsCollector usage (deque(maxlen=1000) for wait times)."""

    def test_wait_times_ring_buffer(self):
        wait_times = deque(maxlen=1000)
        # Simulate recording 1500 wait times
        for i in range(1500):
            wait_times.append(float(i))
        assert len(wait_times) == 1000
        assert wait_times[0] == 500.0
        assert wait_times[-1] == 1499.0

    def test_volatility_ring_buffer(self):
        volatility = deque(maxlen=100)
        for i in range(200):
            volatility.append(i)
        assert len(volatility) == 100
        # Average should reflect recent values only
        avg = sum(volatility) / len(volatility)
        assert avg == pytest.approx(149.5)


class TestSignalBusBatchPattern:
    """Tests mirroring DeterministicSignalBus batch size tracking."""

    def test_batch_size_tracking(self):
        recent_batch_sizes = deque(maxlen=1000)
        running_sum = 0

        # Simulate 1200 ticks with varying batch sizes
        for i in range(1200):
            batch_size = (i % 50) + 1
            if len(recent_batch_sizes) == recent_batch_sizes.maxlen:
                running_sum -= recent_batch_sizes[0]
            recent_batch_sizes.append(batch_size)
            running_sum += batch_size

        assert len(recent_batch_sizes) == 1000
        assert running_sum == sum(recent_batch_sizes)

    def test_pending_queue_unbounded(self):
        """The signal bus _pending queue has no maxlen — verify it grows."""
        pending = deque()
        for i in range(10_000):
            pending.append(("signal", i, {}))
        assert len(pending) == 10_000
        assert pending.maxlen is None
