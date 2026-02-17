import threading
import time

import pytest

from modules.web4_runtime.rtt import RttConfig, RttSession
from modules.web4_runtime.transport import TransportFailover


def test_stress_dropoldest_policy() -> None:
    session = RttSession[str](config=RttConfig(max_queue=100, backpressure_policy="dropoldest"))

    sent = 0
    received = 0

    def sender() -> None:
        nonlocal sent
        for i in range(5000):
            session.send(f"msg-{i}")
            sent += 1

    def receiver() -> None:
        nonlocal received
        time.sleep(0.05)
        while received < 100:
            item = session.receive()
            if item:
                received += 1

    sender_thread = threading.Thread(target=sender)
    receiver_thread = threading.Thread(target=receiver)

    sender_thread.start()
    receiver_thread.start()
    sender_thread.join(timeout=10)
    receiver_thread.join(timeout=10)

    stats = session.stats
    assert stats.dropped_oldest < sent


def test_stress_priority_queue_ordering() -> None:
    session = RttSession[str](config=RttConfig(max_queue=10000, enable_priority_queue=True))

    for i in range(10000):
        session.send(f"msg-{i}", priority=i % 10)

    last_priority = 10
    inversions = 0
    for _ in range(1000):
        item = session.receive()
        if item:
            priority = int(item.split("-")[-1]) % 10
            if priority > last_priority:
                inversions += 1
            last_priority = priority

    assert inversions == 0


def test_stress_failover_recovery_time() -> None:
    class FastMockTransport:
        transport_type = "mock"

        def __init__(self, fail_for: int = 0):
            self.connected = False
            self._fail_for = fail_for

        def connect(self) -> None:
            self.connected = True

        def disconnect(self) -> None:
            self.connected = False

        def send(self, message: str) -> None:
            if message == "__recovery_test__":
                return
            if self._fail_for > 0:
                self._fail_for -= 1
                raise RuntimeError("fail")
            if not self.connected:
                raise RuntimeError("Disconnected")

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

    primary = FastMockTransport(fail_for=3)
    backup = FastMockTransport()

    failover = TransportFailover(primary, backup, failover_threshold=3, recovery_success_threshold=3, recovery_check_interval_s=0)
    failover.connect()

    for _ in range(3):
        with pytest.raises(RuntimeError):
            failover.send("msg")

    failover_start = time.perf_counter()
    for _ in range(3):
        failover.send("msg")
    recovery_time = time.perf_counter() - failover_start

    assert recovery_time < 5.0
