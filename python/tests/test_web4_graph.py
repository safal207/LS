from modules.web4_graph.edge import GraphEdge
from modules.web4_graph.graph_observability import GraphObservabilityHub
from modules.web4_graph.graph_validator import Graph
from modules.web4_graph.node import GraphNode
from modules.web4_graph.routing_rules import RoutingPolicy, next_hop
from modules.web4_graph.trust_graph import GraphTrustFSM, GraphTrustLevel


def test_graph_trust_transitions() -> None:
    trust = GraphTrustFSM()
    assert trust.get("node-a") == GraphTrustLevel.UNKNOWN
    trust.on_handshake("node-a")
    assert trust.get("node-a") == GraphTrustLevel.PROBING
    trust.on_verified("node-a")
    assert trust.get("node-a") == GraphTrustLevel.TRUSTED


def test_graph_routing_rules() -> None:
    trust = GraphTrustFSM()
    trust.on_verified("node-b")
    hop = next_hop("node-b", "node-a", [], trust, RoutingPolicy(max_hops=2))
    assert hop == "node-b"


def test_graph_validation() -> None:
    nodes = {
        "node-a": GraphNode("node-a", "agent", "local://a"),
        "node-b": GraphNode("node-b", "service", "local://b"),
    }
    edges = [GraphEdge("edge-a-b", "node-a", "node-b", "invokes")]
    graph = Graph(nodes=nodes, edges=edges)
    graph.validate()


def test_graph_observability_event() -> None:
    hub = GraphObservabilityHub()
    event = hub.record("service_invoked", "node-a", "node-b", {"service": "svc-b"})
    assert event.node == "node-a"
    assert hub.snapshot()[-1].peer == "node-b"


def test_end_to_end_service_path() -> None:
    trust = GraphTrustFSM()
    trust.on_handshake("node-c")
    trust.on_verified("node-c")
    trust.propagate("node-c", "service-b")
    hop = next_hop("service-b", "agent-a", ["node-c"], trust, RoutingPolicy(max_hops=3))
    assert hop == "service-b"
