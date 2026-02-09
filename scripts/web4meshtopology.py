from python.modules.web4_mesh.peers import Peer, PeerRegistry


def main() -> None:
    registry = PeerRegistry()
    registry.add(Peer("node-a", "local://a"))
    registry.add(Peer("node-b", "local://b"))
    registry.add(Peer("node-c", "local://c"))
    for peer in registry.all_peers():
        print(f"{peer.peer_id} -> {peer.address}")


if __name__ == "__main__":
    main()
