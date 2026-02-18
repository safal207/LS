import gc
import threading
import time

import pytest

from modules.web4_runtime.flow import GlobalFlowController
from modules.web4_runtime.rtt import BackpressureError, RttConfig, RttSession


class _SessionRef:
    pass


def test_global_flow_fixed_limits() -> None:
    flow = GlobalFlowController(total_limit=3, per_session_limit=2, strategy="fixed")
    s1 = _SessionRef()
    flow.register_session(s1)

    assert flow.can_enqueue(s1) is True
    assert flow.try_enqueue(s1) is True
    assert flow.can_enqueue(s1) is True
    assert flow.try_enqueue(s1) is True
    assert flow.can_enqueue(s1) is False


def test_global_flow_proportional_uses_min_limit() -> None:
    flow = GlobalFlowController(total_limit=4, per_session_limit=10, strategy="proportional")
    s1 = _SessionRef()
    s2 = _SessionRef()
    flow.register_session(s1)
    flow.register_session(s2)

    assert flow.try_enqueue(s1) is True
    assert flow.try_enqueue(s1) is True
    assert flow.can_enqueue(s1) is False


def test_global_flow_edge_limits_zero() -> None:
    flow = GlobalFlowController(total_limit=0, per_session_limit=0)
    s1 = _SessionRef()
    flow.register_session(s1)
    assert flow.can_enqueue(s1) is False
    assert flow.try_enqueue(s1) is False


def test_global_flow_concurrent_try_enqueue_respects_total_limit() -> None:
    flow = GlobalFlowController(total_limit=1, per_session_limit=1)
    s1 = _SessionRef()
    s2 = _SessionRef()
    flow.register_session(s1)
    flow.register_session(s2)

    results: list[bool] = []
    lock = threading.Lock()

    def worker(session: _SessionRef) -> None:
        value = flow.try_enqueue(session)
        with lock:
            results.append(value)

    t1 = threading.Thread(target=worker, args=(s1,))
    t2 = threading.Thread(target=worker, args=(s2,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert sum(1 for x in results if x) == 1
    assert flow.total_pending == 1


def test_global_flow_weakref_cleanup_after_gc() -> None:
    flow = GlobalFlowController(total_limit=100, per_session_limit=10)

    session = _SessionRef()
    flow.register_session(session)
    assert flow.try_enqueue(session) is True
    assert flow.total_pending == 1
    assert flow.active_sessions == 1

    del session
    gc.collect()

    # Trigger stale cleanup path.
    probe = _SessionRef()
    flow.register_session(probe)
    assert flow.total_pending == 0


def test_can_enqueue_is_pure_for_unknown_session() -> None:
    flow = GlobalFlowController(total_limit=10, per_session_limit=5)
    ghost = _SessionRef()

    assert flow.active_sessions == 0
    assert flow.can_enqueue(ghost) is False
    assert flow.active_sessions == 0
    assert flow.total_pending == 0


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


def test_dropoldest_swap_keeps_global_pending_consistent() -> None:
    flow = GlobalFlowController(total_limit=10, per_session_limit=10)
    session = RttSession[str](
        config=RttConfig(max_queue=1, backpressure_policy="dropoldest"),
        flow_controller=flow,
    )

    session.send("a")
    assert flow.total_pending == 1

    session.send("b")
    assert session.pending == 1
    assert flow.total_pending == 1
    assert session.receive() == "b"
    assert flow.total_pending == 0


def test_block_policy_wakes_when_global_slot_is_freed() -> None:
    flow = GlobalFlowController(total_limit=1, per_session_limit=1)
    producer = RttSession[str](
        config=RttConfig(max_queue=2, backpressure_policy="error"),
        flow_controller=flow,
    )
    blocked = RttSession[str](
        config=RttConfig(max_queue=2, backpressure_policy="block", block_timeout_s=0.3),
        flow_controller=flow,
    )

    producer.send("first")
    assert flow.total_pending == 1

    result: list[str] = []
    error: list[BaseException] = []

    def sender() -> None:
        try:
            blocked.send("second")
            result.append("ok")
        except BaseException as exc:  # pragma: no cover - diagnostic path
            error.append(exc)

    worker = threading.Thread(target=sender)
    worker.start()
    time.sleep(0.05)

    assert producer.receive() == "first"
    worker.join(timeout=1.0)

    assert error == []
    assert result == ["ok"]
    assert blocked.receive() == "second"
    assert flow.total_pending == 0


def test_flow_cleanup_stress_threadsafe() -> None:
    flow = GlobalFlowController(total_limit=256, per_session_limit=32)
    errors: list[BaseException] = []
    lock = threading.Lock()

    def worker() -> None:
        try:
            for _ in range(200):
                session = _SessionRef()
                flow.register_session(session)
                flow.try_enqueue(session)
                flow.on_dequeue(session)
                flow.unregister_session(session)
        except BaseException as exc:  # pragma: no cover - diagnostic path
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert flow.total_pending == 0
