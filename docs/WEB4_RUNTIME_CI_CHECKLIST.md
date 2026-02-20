# Web4 Runtime CI-Safe Checklist

Use this checklist for PRs touching `python/modules/web4_runtime/**`, `rust_core/**`, or runtime test suites.

## Pre-push local checks

Run from repository root:

```bash
PYTHONPATH=python python -m pytest \
  python/tests/test_web4_runtime.py \
  python/tests/test_web4_mesh.py \
  python/tests/test_web4_graph.py \
  python/tests/test_web4_bio.py
```

```bash
PYTHONPATH=python:python/modules python -m pytest \
  python/tests/test_web4_transport.py \
  python/tests/test_global_flow.py \
  python/tests/test_async_rtt.py \
  python/tests/test_web4_runtime_loadtest.py
```

If Rust bindings are changed:

```bash
cd rust_core
cargo build --release --no-default-features --features python
cargo clippy --all-targets --all-features -- -D warnings
cargo test --all --release --no-default-features --features python-embed
```

Then from repo root:

```bash
PYTHONPATH=python:python/modules python -m pytest python/tests/test_rust_bridge.py
PYTHONPATH=python:python/modules python -m pytest python/tests/test_api_parity.py
```

## Required CI evidence in PR description

- `web4-runtime` workflow result is green.
- If changed: `web4_runtime_extended_load` workflow result is green.
- Mention which runtime suites were run locally.
- If `test_rust_bridge.py` is skipped locally, state whether `ghostgpt_core` was built.

## Transport-agnostic migration checks

- New logic uses `Web4Session` + `TransportBackend` where practical.
- `transport_type` remains present in observability payloads.
- `test_web4_transport.py` passes for RTT and in-memory backends.

## Non-goals for CI-safe PRs

- Long soak tests (1h+) do not belong in default CI.
- Heavy chaos profiles should stay in manual/local runs unless explicitly scoped.
