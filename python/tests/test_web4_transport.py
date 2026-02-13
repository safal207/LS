from modules.web4_runtime import ObservabilityHub, RttConfig, RttSession, RttTransport, TransportRegistry, Web4Session


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
