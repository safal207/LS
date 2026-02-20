from modules.web4_graph.routing_rules import RoutingPolicy, next_hop
from modules.web4_graph.trust_graph import GraphTrustFSM
from modules.web4_mesh.mesh_envelope import MeshEnvelope
from modules.web4_mesh.peers import Peer, PeerRegistry
from modules.web4_mesh.router import MeshForwardingPolicy, MeshRouter
from modules.web4_mesh.trust_mesh import DistributedTrustFSM


def _build_mesh_router(*, destination: str, max_hops: int = 3) -> tuple[MeshRouter, DistributedTrustFSM]:
    registry = PeerRegistry()
    registry.add(Peer("peer-origin", "local://origin"))
    registry.add(Peer(destination, f"local://{destination}"))
    trust = DistributedTrustFSM()
    router = MeshRouter(registry=registry, trust=trust, policy=MeshForwardingPolicy(max_hops=max_hops))
    return router, trust


def test_mesh_graph_interop_happy_path_trusted_destination() -> None:
    destination = "peer-dst"
    router, mesh_trust = _build_mesh_router(destination=destination, max_hops=3)
    graph_trust = GraphTrustFSM()

    mesh_trust.on_verified(destination)
    graph_trust.on_verified(destination)

    envelope = MeshEnvelope("PING", origin="peer-origin", destination=destination, payload={"ok": True})

    routed = router.route(envelope)
    hop = next_hop(destination, "peer-origin", [], graph_trust, RoutingPolicy(max_hops=3))

    assert routed is not None
    assert routed.hops == [destination]
    assert hop == destination


def test_mesh_graph_interop_rejects_blocked_destination() -> None:
    destination = "peer-dst"
    router, mesh_trust = _build_mesh_router(destination=destination, max_hops=3)
    graph_trust = GraphTrustFSM()

    mesh_trust.on_conflict(destination)  # unknown -> blocked
    graph_trust.on_conflict(destination)  # unknown -> blocked

    envelope = MeshEnvelope("PING", origin="peer-origin", destination=destination, payload={})

    assert router.route(envelope) is None
    assert next_hop(destination, "peer-origin", [], graph_trust, RoutingPolicy(max_hops=3)) is None


def test_mesh_graph_interop_rejects_cycle_on_destination_hops() -> None:
    destination = "peer-dst"
    router, mesh_trust = _build_mesh_router(destination=destination, max_hops=3)
    graph_trust = GraphTrustFSM()

    mesh_trust.on_verified(destination)
    graph_trust.on_verified(destination)

    envelope = MeshEnvelope(
        "PING",
        origin="peer-origin",
        destination=destination,
        payload={},
        hops=[destination],
    )

    assert router.route(envelope) is None
    assert next_hop(destination, "peer-origin", [destination], graph_trust, RoutingPolicy(max_hops=3)) is None


def test_mesh_graph_interop_rejects_when_hop_budget_exhausted() -> None:
    destination = "peer-dst"
    router, mesh_trust = _build_mesh_router(destination=destination, max_hops=2)
    graph_trust = GraphTrustFSM()

    mesh_trust.on_verified(destination)
    graph_trust.on_verified(destination)
    hops = ["peer-a", "peer-b"]

    envelope = MeshEnvelope("PING", origin="peer-origin", destination=destination, payload={}, hops=hops)

    assert router.route(envelope) is None
    assert next_hop(destination, "peer-origin", hops, graph_trust, RoutingPolicy(max_hops=2)) is None


def test_mesh_graph_trust_propagation_contract() -> None:
    mesh_trust = DistributedTrustFSM()
    graph_trust = GraphTrustFSM()

    mesh_trust.on_verified("source")
    graph_trust.on_verified("source")

    mesh_link = mesh_trust.propagate("source", "target")
    graph_link = graph_trust.propagate("source", "target")

    assert mesh_link.level.value == "probing"
    assert graph_link.level.value == "probing"
