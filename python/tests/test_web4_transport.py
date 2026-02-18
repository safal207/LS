import pytest

from modules.web4_runtime import (
    ObservabilityHub,
    RttConfig,
    RttSession,
    RttTransport,
    TransportRegistry,
    Web4Session,
)
from modules.web4_runtime.transport import TransportFailover


class _InMemoryTransport:
    def __init__(self, *, transport_type: str = "memory", supports_priority: bool = False) -> None:
        self.transport_type = transport_type
        self._supports_priority = supports_priority
        self._connected = True
        self._queue: list[str] = []
        self._heartbeats = 0
        self._timeouts = 0
        self._sent = 0

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def send(self, message: str, priority: int | None = None) -> None:
        if not self._supports_priority and priority is not None:
            raise TypeError("priority not supported")
        if not self._connected:
            raise RuntimeError("transport disconnected")
        self._sent += 1
        self._queue.append(message)

    def receive(self) -> str | None:
        if not self._queue:
            return None
        return self._queue.pop(0)

    def pending(self) -> int:
        return len(self._queue)

    def stats(self) -> object:
        return {
            "sent": self._sent,
            "heartbeats": self._heartbeats,
            "timeouts": self._timeouts,
        }

    def heartbeat(self) -> None:
        self._heartbeats += 1

    def check_heartbeat_timeout(self) -> bool:
        self._timeouts += 1
        return False

    def health_check(self) -> bool:
        return self._connected


def _run_session_contract(session: Web4Session[str]) -> None:
    assert session.pending() == 0

    session.send("m1")
    session.send("m2")
    assert session.pending() == 2
    assert session.receive() == "m1"
    assert session.receive() == "m2"
    assert session.receive() is None
    assert session.pending() == 0

    session.disconnect()
    with pytest.raises(RuntimeError, match="disconnect"):
        session.send("after-disconnect")

    session.connect()
    session.send("m3")
    assert session.receive() == "m3"
    assert session.pending() == 0


def test_transport_registry_create_and_available() -> None:
    registry: TransportRegistry[str] = TransportRegistry()
    registry.register("rtt", lambda: RttTransport(RttSession[str](config=RttConfig(session_id=1))))

    created = registry.create("rtt")
    assert created.transport_type == "rtt"
    assert registry.available() == ["rtt"]


def test_web4_session_transport_agnostic_flow() -> None:
    transport = RttTransport(RttSession[str](config=RttConfig(session_id=2, max_queue=2)))
    session = Web4Session[str](transport=transport)

    session.send("m1")
    session.send("m2")
    assert session.pending() == 2
    assert session.receive() == "m1"
    assert session.receive() == "m2"


def test_web4_session_observability_includes_transport_type() -> None:
    hub = ObservabilityHub()
    transport = RttTransport(RttSession[str](config=RttConfig(session_id=3)))
    session = Web4Session[str](transport=transport, observability=hub)

    session.send("m1")
    _ = session.receive()

    events = hub.snapshot()
    assert events[0].payload["transport_type"] == "rtt"
    assert events[1].payload["transport_type"] == "rtt"


def test_web4_session_timeout_delegation() -> None:
    transport = RttTransport(RttSession[str](config=RttConfig(session_id=4, heartbeat_timeout_s=0.0)))
    session = Web4Session[str](transport=transport)
    assert session.check_heartbeat_timeout() is True


def test_transport_failover_automatic_switch() -> None:
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

    primary = MockTransport(fail_after=3)
    backup = MockTransport()

    failover = TransportFailover(primary, backup, failover_threshold=3)
    failover.connect()

    for _ in range(3):
        with pytest.raises(RuntimeError):
            failover.send("msg")

    failover.send("msg")
    assert failover._using_backup is True
    assert backup.connected is True


def test_priority_queue_ordering() -> None:
    session = RttSession[str](
        config=RttConfig(max_queue=5, enable_priority_queue=True)
    )

    session.send("low", priority=1)
    session.send("high", priority=10)
    session.send("medium", priority=5)

    assert session.receive() == "high"
    assert session.receive() == "medium"
    assert session.receive() == "low"


@pytest.mark.parametrize(
    ("transport_name", "factory"),
    [
        ("rtt", lambda: RttTransport(RttSession[str](config=RttConfig(session_id=21, max_queue=8)))),
        ("memory", lambda: _InMemoryTransport(transport_type="memory", supports_priority=False)),
        ("memory-priority", lambda: _InMemoryTransport(transport_type="memory-priority", supports_priority=True)),
    ],
)
def test_transport_interchangeability_contract(
    transport_name: str,
    factory,
) -> None:
    """All transport backends must satisfy Web4Session contract semantics."""
    registry: TransportRegistry[str] = TransportRegistry()
    registry.register(transport_name, factory)
    transport = registry.create(transport_name)
    session = Web4Session[str](transport=transport)

    _run_session_contract(session)
