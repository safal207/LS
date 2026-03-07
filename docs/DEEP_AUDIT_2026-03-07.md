# Deep Audit Report — 2026-03-07

## Scope
- Repository-level audit of Python + Rust codebase quality, testability, dependency hygiene, and delivery readiness.
- Focus on **real execution evidence** (pytest/cargo/compile checks) and configuration surface.

## Methods and executed checks
1. `pytest -q`
2. `cargo check --manifest-path rust_core/Cargo.toml`
3. `cargo test --manifest-path rust_core/Cargo.toml`
4. `python -m compileall -q python/modules GhostGPT/modules`
5. Static scan for risky primitives and secret patterns.

## Executive summary
The project has strong feature breadth but low out-of-the-box reliability. Main blockers are:
- fragmented test discovery and environment assumptions,
- mixed dependency contracts between root and subprojects,
- Rust test-mode linking constraints not encoded in docs/tooling,
- repository hygiene gaps for Android/Gradle artifacts.

## Detailed findings

### 1) Critical: test suite is not runnable from clean environment
- Running `pytest -q` produced **70 collection errors** before test execution.
- Errors include missing modules (`PyQt6`, `openai`, `pyaudio`, `modules.nca`) and config loader hard-fail when `PyYAML` is absent.
- This means the repository currently cannot validate baseline health in default CI/dev setup without manual preconditioning.

**Primary evidence in source**:
- Root dependencies are defined, but broad optional stacks are mixed into one file (GUI/audio/ML/cloud). `requirements.txt` includes heavy and platform-sensitive packages (`PyQt6`, `pyaudio`, `torch`, `ltp-client` from git URL). This increases install fragility across CI/OS baselines.
- Config loader intentionally raises at import-time if PyYAML is unavailable, which transforms optional tooling mismatch into hard runtime failure.

### 2) High: test boundary hygiene is weak (integration scripts are test-collected)
- Repository has many `*_test.py` scripts in non-standard folders (including app folders) alongside formal `tests/` tree.
- No `pytest.ini`/`pyproject.toml` with `testpaths` or markers was found, so discovery is broad and unstable.
- Result: manual demo scripts and environment-specific checks are collected as unit tests.

### 3) High: dependency contracts are split and inconsistent
- Root requirements are pinned in many places; `GhostGPT/requirements.txt` is mostly unpinned.
- This creates drift risk: local success can diverge from CI/container reproducibility.
- Git-based dependency in root requirements (`ltp-client @ git+https://...`) introduces supply-chain and determinism concerns (branch tip dependency).

### 4) Medium: Rust test-mode build path is under-specified
- `cargo check` passes for `rust_core`.
- `cargo test` fails at link step with unresolved Python symbols (`PyErr_Print`, `Py_InitializeEx`, etc.).
- `Cargo.toml` documents feature split (`python` extension-module vs `python-embed` auto-initialize), but repo tooling doesn’t enforce or document the test invocation required for this environment.

### 5) Low: repository hygiene gap
- Untracked `apps/android/.gradle/` appears in status, meaning transient Android build cache is not fully ignored at repo level.

## Risk matrix (condensed)
- **Critical**: non-runnable default test lane.
- **High**: ambiguous test discovery, dependency drift.
- **Medium**: Rust test invocation ambiguity.
- **Low**: VCS noise from build caches.

## Recommended remediation roadmap

### Phase A (1–2 days): stabilize baseline validation
1. Add `pytest.ini` with strict `testpaths` and marker taxonomy (`unit`, `integration`, `e2e`, `manual`).
2. Move manual/demo checks out of auto-discovery naming (rename `*_test.py` scripts that are not tests).
3. Introduce dependency tiers:
   - `requirements/base.txt`
   - `requirements/dev.txt`
   - `requirements/gui-audio.txt`
   - optional cloud vendor extras.

### Phase B (2–4 days): deterministic CI and packaging
1. Add lock strategy (pip-tools/uv/poetry lock) for reproducible dependency resolution.
2. Pin Git dependency to immutable commit SHA instead of branch tip.
3. Add CI matrix lanes with minimal + full profiles.

### Phase C (1–2 days): Rust/Python interop clarity
1. Add explicit README/Make target for Rust test invocation in PyO3 context.
2. Gate `cargo test` behavior with documented feature set and required env (`PYO3_PYTHON` etc.).

### Phase D (quick win completed in this PR)
- Ignore Gradle local cache directory to reduce repository noise.

## Operational KPIs to track after remediation
- `pytest -q` collection errors = 0 on clean container.
- Mean setup time to green tests < 15 min.
- Dependency resolution reproducibility (hash/lock drift) = 0 unexpected changes.
- CI pass rate across minimal/full profiles >= 95% for main branch.

