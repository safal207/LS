import queue

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
from modules.web4_runtime.protocol_router import Web4ProtocolRouter
from modules.web4_runtime.rtt import BackpressureError, DisconnectedError, RttConfig, RttSession


def test_rtt_backpressure_and_reconnect() -> None:
    session = RttSession[str](config=RttConfig(max_queue=1))
    session.send("first")
    with pytest.raises(BackpressureError):
        session.send("second")
    session.disconnect()
    with pytest.raises(DisconnectedError):
        session.send("third")
    session.reconnect()
    session.send("third")
    assert session.receive() == "third"


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


def test_rust_web4_rtt_binding() -> None:
    ghostgpt_core = pytest.importorskip("ghostgpt_core")
    Web4RttBinding = ghostgpt_core.Web4RttBinding

    binding = Web4RttBinding(1)
    binding.send("first")
    assert binding.receive() == "first"

    binding.send("buffered")
    with pytest.raises(RuntimeError):
        binding.send("overflow")

    binding.disconnect()
    with pytest.raises(RuntimeError):
        binding.send("offline")
    assert binding.receive() is None

    binding.connect()
    binding.send("reconnected")
    assert binding.receive() == "reconnected"
