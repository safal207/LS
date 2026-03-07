# Contributing to GhostGPT

First off, thank you for considering contributing to GhostGPT! It's people like you that make GhostGPT such a great tool for the global community.

## 🌟 What We're Looking For

We are building the future of local cognitive systems (**GhostOS**). We are specifically looking for experts and enthusiasts in:

- **Rust Systems Programming**: Performance optimizations, SIMD, and cross-platform hardware acceleration.
- **Cognitive Architecture**: Implementing memory consolidation, emotional models (Amygdala), and agentic loops.
- **AR/VR & Vision**: Real-time scene understanding, zero-copy frame processing, and spatial awareness.
- **Privacy & Security**: Zero-knowledge proofs, PII redaction, and local-first safety protocols.

## 🏗 Architecture Guidelines

GhostGPT uses a **Hexagon Core** (12-layer) architecture. When contributing, please keep the following in mind:

1.  **Core Independence**: The `hexagon_core` should remain independent of specific UI or transport implementations.
2.  **Rust for Performance**: If a task is computationally expensive (e.g., pattern matching, image processing), implement it in `rust_core` and provide a Python bridge.
3.  **Local-First**: We avoid external API dependencies unless absolutely necessary and always provide a local fallback.
4.  **Event-Driven**: Use the internal event bus for communication between subsystems.

## 🚀 Getting Started

1.  **Fork the repo** and create your branch from `main`.
2.  **Setup the environment**:
    ```bash
    python -m venv venv
    source venv/bin/activate
    pip install "ghostgpt-core[full]"
    ```
3.  **Build the Rust components**:
    ```bash
    maturin develop --features vision
    ```

## 🧪 Testing & Benchmarks

We maintain high standards for code quality. **All PRs must include tests.**

- **Python Tests**: Run using `pytest`.
  ```bash
  PYTHONPATH=python/modules python -m pytest tests/
  ```
- **Rust Tests**:
  ```bash
  cd rust_core && cargo test --no-default-features --features python-embed
  ```
- **Benchmarks**: Use `pytest-benchmark` for Python and `criterion` for Rust.

## ✅ Pull Request Checklist

Before submitting a PR, please ensure:

- [ ] Code follows the existing style (follow Ruff style (CI uses ruff autofix)).
- [ ] Type hints are used everywhere in Python.
- [ ] Rust code is linted with `clippy`.
- [ ] Tests cover at least 90% of the new logic.
- [ ] Documentation is updated (including bilingual README if applicable).
- [ ] All CI checks are passing.

## 💬 Communication

- **Issues**: Use GitHub Issues for bug reports and feature requests.
- **Discussions**: Use GitHub Discussions for architecture brainstorming.

Together, we're building GhostOS. 🚀
