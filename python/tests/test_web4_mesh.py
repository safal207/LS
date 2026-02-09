import pytest

from python.modules.web4_mesh.mesh_envelope import MeshEnvelope
from python.modules.web4_mesh.mesh_rtt import MeshRttConfig, MeshRttSession, MeshBackpressureError, MeshDisconnectedError
from python.modules.web4_mesh.observability_mesh import MeshObservabilityHub
from python.modules.web4_mesh.peers import Peer, PeerRegistry
from python.modules.web4_mesh.router import MeshForwardingPolicy, MeshRouter
from python.modules.web4_mesh.trust_mesh import DistributedTrustFSM, TrustLevel


def test_mesh_router_routing() -> None:
    registry = PeerRegistry()
    registry.add(Peer("peer-a", "local://a"))
    registry.add(Peer("peer-b", "local://b"))
    trust = DistributedTrustFSM()
    trust.on_verified("peer-b")
    router = MeshRouter(registry=registry, trust=trust, policy=MeshForwardingPolicy(max_hops=2))
    envelope = MeshEnvelope("HELLO", origin="peer-a", destination="peer-b", payload={"hi": True})
    routed = router.route(envelope)
    assert routed is not None
    assert routed.hops == ["peer-b"]


def test_mesh_trust_propagation() -> None:
    trust = DistributedTrustFSM()
    trust.on_verified("peer-a")
    link = trust.propagate("peer-a", "peer-b")
    assert link.level in (TrustLevel.PROBING, TrustLevel.TRUSTED)


def test_mesh_rtt_backpressure() -> None:
    rtt = MeshRttSession[str](config=MeshRttConfig(max_queue=1))
    rtt.send("one")
    with pytest.raises(MeshBackpressureError):
        rtt.send("two")
    rtt.disconnect()
    with pytest.raises(MeshDisconnectedError):
        rtt.send("three")


def test_mesh_observability() -> None:
    hub = MeshObservabilityHub()
    event = hub.record("mesh_routed", {"peer": "peer-a"})
    assert event.event_type == "mesh_routed"
    assert hub.snapshot()[-1].payload["peer"] == "peer-a"
