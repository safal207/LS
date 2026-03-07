# Rust Bridge Local Setup

This note explains how to run `python/tests/test_rust_bridge.py` locally.

## Why this exists

`test_rust_bridge.py` includes binding-level tests for the optional Rust Python extension module `ghostgpt_core`.

- In CI: missing `ghostgpt_core` is a failure.
- Locally: if no extension artifact is found, binding tests are skipped so fallback tests can still run.

## Build the extension

From repository root:

```bash
cd rust_core
cargo build --release --no-default-features --features python
```

Expected artifact location:

- `rust_core/target/release/ghostgpt_core*`
- or `rust_core/target/release/libghostgpt_core*`

## Run bridge tests

From repository root:

```bash
PYTHONPATH=python:python/modules python -m pytest python/tests/test_rust_bridge.py
```

## Platform notes

- Linux CI uses `cargo build --release --no-default-features --features python`.
- On Windows, ensure your Rust toolchain matches installed linker tooling:
  - `x86_64-pc-windows-msvc` requires Visual Studio Build Tools (`link.exe`).
  - `x86_64-pc-windows-gnu` requires MinGW runtime/link libs.

If the module cannot be imported locally and no artifact exists, pytest will skip binding-only checks and still execute fallback-path tests.


## Optional audio_core extension (Voice Pipeline v2)

Build PyO3 extension for low-latency audio DSP:

```bash
cd rust/audio_core
maturin develop --release
```

If `audio_core` cannot be imported, Python fallback remains active (`python/modules/audio/rust_core.py`).
