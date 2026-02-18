import pytest

from modules.web4_runtime.flow import GlobalFlowController
from modules.web4_runtime.rtt import BackpressureError, RttConfig, RttSession


def test_global_flow_fixed_limits() -> None:
    flow = GlobalFlowController(total_limit=3, per_session_limit=2, strategy="fixed")
    s1 = object()
    flow.register_session(s1)

    assert flow.can_enqueue(s1) is True
    flow.on_enqueue(s1)
    assert flow.can_enqueue(s1) is True
    flow.on_enqueue(s1)
    assert flow.can_enqueue(s1) is False


def test_global_flow_proportional_uses_min_limit() -> None:
    flow = GlobalFlowController(total_limit=4, per_session_limit=10, strategy="proportional")
    s1 = object()
    s2 = object()
    flow.register_session(s1)
    flow.register_session(s2)

    # proportional limit = total_limit // active_sessions = 2
    assert flow.can_enqueue(s1) is True
    flow.on_enqueue(s1)
    assert flow.can_enqueue(s1) is True
    flow.on_enqueue(s1)
    assert flow.can_enqueue(s1) is False


def test_rtt_session_registers_with_flow_controller() -> None:
    flow = GlobalFlowController(total_limit=10, per_session_limit=5)
    session = RttSession[str](config=RttConfig(max_queue=2), flow_controller=flow)
    assert flow.can_enqueue(session) is True


def test_rtt_session_send_respects_global_flow_limit() -> None:
    flow = GlobalFlowController(total_limit=100, per_session_limit=1)
    session = RttSession[str](config=RttConfig(max_queue=10, backpressure_policy="error"), flow_controller=flow)

    session.send("a")
    assert flow.can_enqueue(session) is False

    with pytest.raises(BackpressureError, match="backpressure"):
        session.send("b")


def test_rtt_session_receive_updates_global_flow_counters() -> None:
    flow = GlobalFlowController(total_limit=100, per_session_limit=1)
    session = RttSession[str](config=RttConfig(max_queue=10, backpressure_policy="error"), flow_controller=flow)

    session.send("a")
    assert flow.can_enqueue(session) is False
    assert session.receive() == "a"
    assert flow.can_enqueue(session) is True


def test_rtt_session_reconnect_resets_global_flow_counters() -> None:
    flow = GlobalFlowController(total_limit=100, per_session_limit=1)
    session = RttSession[str](config=RttConfig(max_queue=10, backpressure_policy="error"), flow_controller=flow)

    session.send("a")
    assert flow.can_enqueue(session) is False
    session.disconnect()
    session.reconnect()
    assert flow.can_enqueue(session) is True
