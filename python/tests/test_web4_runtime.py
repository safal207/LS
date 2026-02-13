import queue
import threading
import time

import pytest

from modules.agent.loop import AgentLoop
from modules.protocols.cip import CipIdentity, CipState, build_envelope
from modules.protocols.hcp import HcpHumanState, HcpIdentity
from modules.protocols.lip import LipIdentity, LipSource
from modules.protocols.trust import TrustFSM, TrustState
from modules.web4_runtime.agent_integration import AgentLoopAdapter
from modules.web4_runtime.cip_runtime import CipRuntime
from modules.web4_runtime.hcp_runtime import HcpRuntime, HcpPolicy
from modules.web4_runtime.lip_runtime import LipRuntime
from modules.web4_runtime.observability import ObservabilityHub
from modules.web4_runtime.protocol_router import Web4ProtocolRouter
from modules.web4_runtime.rtt import BackpressureError, DisconnectedError, RttConfig, RttSession
from time import monotonic


def test_qos_dropoldest_overflow() -> None:
    session = RttSession[str](config=RttConfig(max_queue=2, backpressure_policy="dropoldest"))
    session.send_batch(["a", "b", "c"])
    assert session.receive() == "b"
    assert session.receive() == "c"
    assert session.stats.dropped_oldest == 1
    assert session.stats.enqueued == 3


def test_qos_dropnewest_overflow() -> None:
    session = RttSession[str](config=RttConfig(max_queue=2, backpressure_policy="dropnewest"))
    session.send_batch(["a", "b", "c"])
    assert session.receive() == "a"
    assert session.receive() == "b"
    assert session.receive() is None
    assert session.stats.dropped_newest == 1
    assert session.stats.enqueued == 2


def test_qos_block_timeout() -> None:
    session = RttSession[str](config=RttConfig(max_queue=1, backpressure_policy="block", block_timeout_s=0.01))
    session.send("a")
    with pytest.raises(BackpressureError, match="timeout"):
        session.send("b")
    assert session.stats.errors == 1
    assert session.stats.blocked == 1


def test_rtt_stats_consistency() -> None:
    session = RttSession[str](config=RttConfig(max_queue=2, backpressure_policy="dropoldest"))
    session.send_batch(["a", "b", "c", "d"])
    stats = session.stats
    assert stats.attempted == 4
    assert stats.enqueued == 4
    assert stats.overflow_events == 2
    assert stats.max_queue_len >= session.pending


def test_rtt_backpressure_and_reconnect() -> None:
    session = RttSession[str](config=RttConfig(max_queue=1, backpressure_policy="error"))
    session.send("first")
    with pytest.raises(BackpressureError):
        session.send("second")
    session.disconnect()
    with pytest.raises(DisconnectedError):
        session.send("third")
    session.reconnect()
    session.send("third")
    assert session.receive() == "third"


def test_rtt_block_policy_waits_for_space() -> None:
    session = RttSession[str](config=RttConfig(max_queue=1, backpressure_policy="block", block_timeout_s=0.2))
    session.send("a")

    def delayed_receive() -> None:
        time.sleep(0.05)
        assert session.receive() == "a"

    worker = threading.Thread(target=delayed_receive)
    worker.start()
    session.send("b")
    worker.join(timeout=1)

    assert session.receive() == "b"
    assert session.stats.blocked == 1

def test_block_policy_spurious_wakeup_resilience() -> None:
    session = RttSession[str](
        config=RttConfig(max_queue=1, backpressure_policy="block", block_timeout_s=0.5)
    )

    session.send("a")

    def consumer() -> None:
        time.sleep(0.1)
        assert session.receive() == "a"

    worker = threading.Thread(target=consumer)
    worker.start()

    with session._condition:
        session._condition.notify_all()

    session.send("b")
    worker.join(timeout=1)

    assert session.receive() == "b"
    assert session.stats.blocked == 1
    assert session.stats.errors == 0


def test_unregister_and_clear_session_hooks() -> None:
    session = RttSession[str](config=RttConfig(session_id=9))
    events: list[tuple[str, int]] = []

    def on_open(sid: int) -> None:
        events.append(("open", sid))

    def on_close(sid: int) -> None:
        events.append(("close", sid))

    session.register_on_session_open(on_open)
    assert events == [("open", 9)]
    session.unregister_on_session_open(on_open)
    session.register_on_session_close(on_close)
    session.clear_session_hooks()

    session.disconnect()
    session.reconnect()

    assert events == [("open", 9)]

def test_hook_reentrancy_guard_prevents_recursive_emit() -> None:
    session = RttSession[str](config=RttConfig(session_id=77))
    events: list[tuple[str, int]] = []

    def on_close(sid: int) -> None:
        events.append(("close", sid))
        # would recurse into session_close emit if no guard exists
        session.disconnect(reason="nested")

    session.register_on_session_close(on_close)
    session.disconnect(reason="manual")

    assert events == [("close", 77)]

def test_session_lifecycle_hooks_and_observability() -> None:
    hub = ObservabilityHub()
    events: list[tuple[str, int]] = []
    session = RttSession[str](
        config=RttConfig(session_id=42, heartbeat_timeout_s=1.0),
        observability=hub,
    )

    session.register_on_session_open(lambda sid: events.append(("open", sid)))
    session.register_on_session_close(lambda sid: events.append(("close", sid)))
    session.register_on_heartbeat_timeout(lambda sid: events.append(("timeout", sid)))

    session.disconnect()
    session.reconnect()
    session._heartbeat_at = monotonic() - 2.0
    assert session.check_heartbeat_timeout() is True

    assert events == [("open", 42), ("close", 42), ("open", 42), ("timeout", 42), ("close", 42)]
    observed = [(evt.event_type, evt.payload["session_id"]) for evt in hub.snapshot()]
    assert observed == [("session_close", 42), ("session_open", 42), ("heartbeat_timeout", 42), ("session_close", 42)]


def test_cip_handshake_trust_fsm() -> None:
    trust = TrustFSM()
    runtime = CipRuntime(CipIdentity("a", "fp-a"), trust)
    receiver = CipIdentity("b", "fp-b")
    hello = runtime.build_hello(receiver, CipState("online", 1))
    transition = runtime.handle_envelope(hello)
    assert transition is not None
    assert trust.state == TrustState.PROBING
    fact = build_envelope("FACT_CONFIRM", runtime.identity, receiver, {"fact": "ok"})
    runtime.handle_envelope(fact)
    assert trust.state == TrustState.TRUSTED


def test_hcp_consent_pacing() -> None:
    runtime = HcpRuntime(HcpIdentity("a", "fp-a"), policy=HcpPolicy(max_pressure=5))
    denied = HcpHumanState("present", "calm", 5, 6, "test", "granted")
    assert runtime.allow_interaction(denied) is False
    no_consent = HcpHumanState("present", "calm", 5, 3, "test", "denied")
    assert runtime.allow_interaction(no_consent) is False
    ok = HcpHumanState("present", "calm", 5, 3, "test", "granted")
    assert runtime.allow_interaction(ok) is True


def test_lip_deferred_acceptance() -> None:
    runtime = LipRuntime(LipIdentity("a", "fp-a"))
    receiver = LipIdentity("b", "fp-b")
    source = LipSource("https://example.com", "tier1", "now")
    envelope = runtime.build_source_update(receiver, {"data": 1}, source)
    deferred = runtime.defer_if_untrusted(envelope, TrustState.UNTRUSTED)
    assert deferred is True
    released = runtime.release_deferred(TrustState.TRUSTED)
    assert released == [envelope]


def test_protocol_router_routing() -> None:
    trust = TrustFSM()
    cip = CipRuntime(CipIdentity("a", "fp-a"), trust)
    hcp = HcpRuntime(HcpIdentity("a", "fp-a"))
    lip = LipRuntime(LipIdentity("a", "fp-a"))
    router = Web4ProtocolRouter(cip=cip, hcp=hcp, lip=lip)
    receiver = CipIdentity("b", "fp-b")
    hello = cip.build_hello(receiver)
    result = router.dispatch(hello)
    assert result.router_result.handled is True


def test_agent_loop_integration() -> None:
    trust = TrustFSM()
    cip = CipRuntime(CipIdentity("a", "fp-a"), trust)
    hcp = HcpRuntime(HcpIdentity("a", "fp-a"))
    lip = LipRuntime(LipIdentity("a", "fp-a"))
    router = Web4ProtocolRouter(cip=cip, hcp=hcp, lip=lip)
    output = queue.Queue()
    agent_loop = AgentLoop(handler=lambda text: f"echo:{text}", output_queue=output)
    adapter = AgentLoopAdapter(agent_loop=agent_loop, router=router)
    receiver = CipIdentity("b", "fp-b")
    envelope = cip.build_hello(receiver)
    result = adapter.handle_envelope(envelope)
    assert result["handled"] is True
    assert output.get(timeout=1) == "echo:{'handshake': 'hello'}"
