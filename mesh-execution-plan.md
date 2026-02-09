# Web4 Mesh Milestone Execution Plan

## Entry Point & Inputs

- Primary milestone file: `docs/CIPRUNTIMEINTEGRATION_ISSUE.md`.
- Mesh generator contract: `WEB4MESHEXECUTIONPLANGENERATOR.md`.
- Existing Web4 runtime modules in `python/modules/web4_runtime/`.

## Architecture Overview

- **Mesh routing**: `MeshRouter` + `MeshForwardingPolicy` using `PeerRegistry`.
- **Envelope**: `MeshEnvelope` carries hop metadata for multi-peer routing.
- **Trust propagation**: `DistributedTrustFSM` handles peer trust levels and propagation.
- **Mesh RTT**: `MeshRttSession` provides minimal backpressure-aware transport.
- **Observability**: `MeshObservabilityHub` records routing/peer events.
- **CLI tools**: inspect, topology, and demo scripts in `scripts/`.

## Sub-Issues (Planned & Implemented)

### MeshRouter
- Implement router with hop limits and blocked-peer checks.

### PeerRegistry
- Provide peer registration and lookup utilities.

### MeshEnvelope
- Provide envelope with hop tracking and serialization.

### MeshForwardingPolicy
- Configure hop limits and broadcast behavior.

### CIP Mesh Handshake
- Use mesh envelope + trust propagation to model handshake.

### Distributed TrustFSM
- Implement `DistributedTrustFSM` with propagation hooks.

### Mesh RTT
- Implement `MeshRttSession` with backpressure + reconnect.

### Mesh Observability
- Implement `MeshObservabilityHub` for event logging.

### Mesh CLI Tools
- Add `scripts/web4meshdemo.py`, `scripts/web4meshinspect.py`, `scripts/web4meshtopology.py`.

### Mesh Tests
- Add `python/tests/test_web4_mesh.py` covering routing, trust, RTT, and observability.

### Integration with Web4 Runtime
- Mesh modules live alongside `web4_runtime` for shared use.

## Risks & Mitigations

- **Mesh scope creep**: keep hop limit small and use in-memory registries.
- **Trust propagation complexity**: limit to minimal transitions for MVP.

## Done Criteria

- Mesh execution plan present.
- Mesh modules + CLI tools implemented.
- Tests pass locally and in CI.
