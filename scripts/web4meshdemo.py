from python.modules.web4_mesh.mesh_envelope import MeshEnvelope
from python.modules.web4_mesh.peers import Peer, PeerRegistry
from python.modules.web4_mesh.router import MeshRouter
from python.modules.web4_mesh.trust_mesh import DistributedTrustFSM


def main() -> None:
    registry = PeerRegistry()
    registry.add(Peer("node-a", "local://a"))
    registry.add(Peer("node-b", "local://b"))
    registry.add(Peer("node-c", "local://c"))

    trust = DistributedTrustFSM()
    trust.on_verified("node-b")
    trust.on_verified("node-c")

    router = MeshRouter(registry=registry, trust=trust)
    envelope = MeshEnvelope("MESH_HELLO", origin="node-a", destination="node-b", payload={"mesh": "hi"})
    routed = router.route(envelope)
    print("Mesh demo routed:", routed.to_dict() if routed else None)


if __name__ == "__main__":
    main()
