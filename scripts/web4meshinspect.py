from python.modules.web4_mesh.observability_mesh import MeshObservabilityHub


def main() -> None:
    hub = MeshObservabilityHub()
    hub.record("mesh_boot", {"status": "ok"})
    hub.record("mesh_peer_added", {"peer": "node-a"})
    for event in hub.snapshot():
        print(event.event_type, event.payload)


if __name__ == "__main__":
    main()
