# Web4 Runtime Milestone Execution Plan

## Entry Point & Inputs

- Primary milestone file: `docs/CIP_RUNTIME_INTEGRATION_ISSUE.md` (requested in spec; **not present in repo** at time of execution).  
- Generator contract: `WEB4EXECUTIONPLAN_GENERATOR.md`.  
- Supplemental specs used: `docs/CIP_SPEC.md`, `docs/HCP_SPEC.md`, `docs/LIP_SPEC.md`.  

## Architecture Overview

- **Protocol layer**: existing CIP/HCP/LIP envelope builders + validation in `python/modules/protocols/`.
- **Runtime layer**: new Web4 runtime adapters (RTT, CIP/HCP/LIP runtimes, router, observability).
- **Integration layer**: adapter that binds ProtocolRouter to `AgentLoop`.
- **Rust bridge**: minimal PyO3 RTT binding to provide a native scaffold.
- **CLI demos**: two runnable scripts demonstrating the handshake + mesh/deferred flows.
- **Tests**: unit + integration coverage for handshake, trust, backpressure, deferred acceptance, and AgentLoop integration.

## Sub-Issues (Planned & Implemented)

### RTT
- Implement `RttSession` with reconnect + backpressure.
- Add minimal PyO3 RTT binding (Rust scaffold).
- Tests: reconnect/backpressure.

### CIP
- Implement `CipRuntime` handshake handling.
- Tests: HELLO → TrustFSM transition + fact confirmation.

### HCP
- Implement `HcpRuntime` consent/pacing policy checks.
- Tests: consent + pressure gating.

### LIP
- Implement `LipRuntime` deferred acceptance queue.
- Tests: defer until trusted.

### ProtocolRouter
- Implement Web4 router wrapper over existing `ProtocolRouter`.
- Tests: route HELLO/HUMAN_STATE/SOURCE_UPDATE.

### TrustFSM
- Use existing TrustFSM in protocols; validate transitions via CIP tests.

### AgentLoop
- Adapter that routes envelopes into `AgentLoop` handlers.
- Tests: integration with output queue.

### Observability
- Lightweight `ObservabilityHub` to record routing events.

### Tests
- Add `python/tests/test_web4_runtime.py` for unit + integration checks.

### CLI Tools
- Add `scripts/web4_demo.py` and `scripts/web4_mesh_demo.py`.

## Risks & Mitigations

- **Missing CIP runtime issue file**: noted; used available specs instead. (Action: add the missing file or update generator if renamed.)
- **CI lint/type-check scope**: restrict to new Web4 modules to avoid breaking existing code.

## Done Criteria

- Execution plan, scaffolding, CLI demos, tests, and CI workflow are present.
- Tests pass locally (`pytest python/tests/test_web4_runtime.py`).
- Rust build passes in CI (`cargo build` in `rust_core`).
