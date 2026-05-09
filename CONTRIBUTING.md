# Contributing to LS

Thank you for considering a contribution. LS needs both engineering work and clear public explanation: the project will grow faster if visitors can understand the landing page, run the demo, and find small tasks quickly.

Start here:

- Public site: https://safal207.github.io/LS/
- Roadmap: [ROADMAP.md](ROADMAP.md)
- Community tasks: [docs/COMMUNITY_TASKS.md](docs/COMMUNITY_TASKS.md)
- GitHub Pages setup: [docs/GITHUB_PAGES_SETUP.md](docs/GITHUB_PAGES_SETUP.md)

## What We Are Looking For

We are building a local-first coordination and oversight layer for multi-agent AI work. We are especially looking for:

- Landing page clarity: copy, diagrams, mobile layout, and before/after examples.
- Documentation: simple setup paths and practical examples.
- Runtime reliability: tests, fallback behavior, and review workflows.
- Safety and oversight: replayable traces, quality gates, and evidence packages.
- Rust/Python performance work where it supports the runtime.

Good first task list: [docs/COMMUNITY_TASKS.md](docs/COMMUNITY_TASKS.md)

## Architecture Guidelines

GhostGPT uses a **Hexagon Core** (12-layer) architecture. When contributing, please keep the following in mind:

1.  **Core Independence**: The `hexagon_core` should remain independent of specific UI or transport implementations.
2.  **Rust for Performance**: If a task is computationally expensive (e.g., pattern matching, image processing), implement it in `rust_core` and provide a Python bridge.
3.  **Local-First**: We avoid external API dependencies unless absolutely necessary and always provide a local fallback.
4.  **Event-Driven**: Use the internal event bus for communication between subsystems.

## Getting Started

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

## Landing Page Only

If you only want to work on the public site:

```bash
cd ghostgpt-ls-landing
npm ci
npm run dev
npm run build
```

Local URL:

```text
http://127.0.0.1:5173/
```

## Testing & Benchmarks

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

## Pull Request Checklist

Before submitting a PR, please ensure:

- [ ] Code follows the existing style (follow Ruff style (CI uses ruff autofix)).
- [ ] Type hints are used everywhere in Python.
- [ ] Rust code is linted with `clippy`.
- [ ] Tests cover at least 90% of the new logic.
- [ ] Documentation is updated (including bilingual README if applicable).
- [ ] All CI checks are passing.

## Communication

- **Issues**: Use GitHub Issues for bug reports and feature requests.
- **Discussions**: Use GitHub Discussions for architecture brainstorming.

Small, focused PRs are best. For landing page changes, include a screenshot or a short before/after note.
