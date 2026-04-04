# LiminalQA Test Strategy

## Purpose

Use `LiminalQAengineer` as a test intelligence and run-analysis layer for this repository, while keeping `pytest`, `cargo test`, and `pytest-cov` as the execution and coverage tools.

This distinction matters:

- `pytest` and `cargo test` execute checks
- `coverage.py` / `pytest-cov` measure coverage
- `LiminalQAengineer` classifies failures, tracks flakiness, compares runs over time, and recommends merge policy

For this repository, LiminalQA should answer:

- is a failure a real regression or a flaky/infrastructure issue
- which suites are critical for merge blocking
- where runtime is degrading
- which tests should be quarantined, retried, or promoted into a stricter gate

## Current Repository Reality

As of 2026-04-03, the repository already has a large and fragmented test surface:

- `tests/unit/`: 80 test files
- `tests/smoke/`: 32 test files
- `tests/e2e/`: 9 test files
- `tests/*.py`: 35 root-level test files
- `python/tests/`: 89 test files

Current CI is split across multiple workflows:

- `.github/workflows/ci.yml`
- `.github/workflows/mesh-tests.yml`
- `.github/workflows/web4_runtime_ci.yml`

That gives execution, but not a single quality memory. There is no central history of:

- flaky node IDs
- pass-rate drift over time
- duration regressions by suite
- merge policy based on confidence rather than a single red build

## Strategic Positioning

Do not replace the current test stack. Wrap it.

Recommended architecture:

1. Keep existing `pytest` and Rust test commands.
2. Standardize machine-readable outputs per workflow:
   - JUnit XML
   - coverage XML
   - retained logs/artifacts
3. Send run and test facts into `LiminalQAengineer`.
4. Let LiminalQA produce a decision packet:
   - `NEW_BUG`
   - `FLAKE`
   - `KNOWN_ISSUE`
   - `WARN`
   - `BLOCK`
5. Use that packet for CI gating and triage, not for raw execution.

## Test Lanes

The repository is too large for one uniform policy. Split it into lanes with distinct merge behavior.

| Lane | Sources | Goal | Merge Policy | Liminal Plan |
|---|---|---|---|---|
| `critical-smoke` | `tests/smoke/`, key root smoke-style tests | fast signal on critical paths | block on confident regression | `critical-smoke` |
| `core-unit` | `tests/unit/`, stable root unit tests | deterministic logic validation | warn on isolated flake, block on repeated regression | `core-unit` |
| `python-runtime` | `python/tests/` for `web4`, `graph`, `llm`, `hexagon_core` | subsystem contracts and runtime correctness | block on critical domains, warn on non-critical drift | `python-runtime` |
| `mesh-runtime` | current mesh workflow targets | mesh transport and service integration | block | `mesh-runtime` |
| `rust-bridge` | `python/tests/test_rust_bridge.py`, `test_api_parity.py`, `rust_core` tests | Python/Rust parity and bridge stability | block after baseline is trusted | `rust-bridge` |
| `e2e` | `tests/e2e/` | user-facing path validation | warn initially, block only for stabilized scenarios | `e2e` |
| `optional-hardware` | OCR/audio/GUI/device-sensitive tests | environment-sensitive coverage | never hard-block by default | `optional-hardware` |

## Integration Model

### Phase 1: Passive Observability

Goal: no policy changes, only memory.

Actions:

- add `pytest-liminalqa` to CI test jobs
- send every `pytest` session to LiminalQA ingest
- keep existing GitHub pass/fail behavior unchanged
- upload JUnit XML, coverage XML, and logs as artifacts

Exit criteria:

- 2-3 weeks of run history
- stable mapping from workflow -> suite -> nodeid
- first flaky candidates identified

### Phase 2: Baselines and Classification

Goal: teach the system what "normal" means for this repo.

Actions:

- define a stable `LIMINALQA_PLAN` per workflow
- map each workflow job to one quality lane
- ingest retry counts, duration, exit code, and selected artifact links
- mark known environment-sensitive tests separately

Recommended metadata mapping:

- `System`: `LS`
- `Build`: GitHub run + commit SHA
- `Run`: workflow job attempt
- `Test`: pytest nodeid or Rust test name
- `Artifact`: JUnit XML, coverage XML, logs, screenshots
- `Signal`: duration, retry count, timeout, coverage delta, rust build status

Exit criteria:

- duration baseline per lane
- pass-rate baseline per lane
- first list of quarantined flaky tests

### Phase 3: Merge Intelligence

Goal: move from red/green to evidence-based policy.

Rules:

- `critical-smoke`, `mesh-runtime`, `rust-bridge`:
  block only when LiminalQA confidence indicates likely regression
- `e2e`, `optional-hardware`:
  default to warn unless a failure pattern becomes stable and reproducible
- repeated flake with high confidence:
  warn + auto-label + quarantine candidate
- duration degradation without functional regression:
  warn and create performance issue, do not block by default

Exit criteria:

- false merge blocks reduced
- repeated flaky tests identified automatically
- triage time per CI failure reduced

### Phase 4: Coverage-Guided Expansion

Goal: use LiminalQA findings to improve coverage where it matters.

Actions:

- compare failure-prone areas with low coverage reports
- prioritize new tests for:
  - `agent/`
  - `python/modules/web4_runtime/`
  - `python/modules/web4_mesh/`
  - `python/modules/hexagon_core/`
  - `python/modules/llm/`
- treat "critical but poorly covered" modules as mandatory backlog

Important:

LiminalQA does not replace `pytest-cov`; it tells you where additional coverage pays off the most.

## Recommended CI Changes

### 1. Standardize pytest output

Every Python workflow should emit at least:

```bash
pytest ... \
  --junitxml=artifacts/junit.xml \
  --cov=<target> \
  --cov-report=xml:artifacts/coverage.xml
```

`mesh-tests.yml` already does this well and should be the template for the other Python workflows.

### 2. Add LiminalQA plugin in passive mode

Example pattern for Python jobs:

```bash
pip install pytest-liminalqa

pytest ... \
  --liminalqa-url "$LIMINALQA_URL" \
  --liminalqa-plan "mesh-runtime"
```

If the plugin remains too minimal for your needs, keep it as the fast path and add a second adapter that posts:

- coverage summary
- artifact URLs
- retry metadata
- workflow/job labels

### 3. Normalize suite naming

Use stable plan names across all runs:

- `critical-smoke`
- `core-unit`
- `python-runtime`
- `mesh-runtime`
- `rust-bridge`
- `e2e`
- `optional-hardware`

This is necessary for baseline quality. Renaming plans frequently will poison trend analysis.

### 4. Separate hard blockers from noisy tests

Move environment-sensitive tests behind explicit markers, for example:

- `@pytest.mark.hardware`
- `@pytest.mark.gui`
- `@pytest.mark.network`
- `@pytest.mark.slow`

Then run them in dedicated lanes instead of mixing them with merge blockers.

## What To Instrument First

Start with the workflows already closest to production quality:

1. `mesh-tests.yml`
2. `web4_runtime_ci.yml`
3. `ci.yml`

Reason:

- they already represent distinct domains
- they are active merge surfaces
- they have clearer ownership and signal value than the full repo test sprawl

## Success Metrics

Track these metrics for 30 days after rollout:

- median triage time per CI failure
- number of flaky tests identified
- false positive merge blocks
- percentage of failures classified as regression vs flake vs infra
- p95 duration drift by lane
- critical-module coverage trend

## Concrete Rollout Plan

Week 1:

- enable JUnit + coverage XML in every Python workflow
- deploy LiminalQA ingest locally or in Docker
- connect `mesh-tests.yml` in passive mode

Week 2:

- connect `web4_runtime_ci.yml`
- define lane names and artifact retention policy
- start collecting flake and duration baselines

Week 3:

- connect `ci.yml`
- mark hardware/GUI/network-sensitive tests
- quarantine first confirmed flaky tests

Week 4:

- enable merge warnings from LiminalQA
- keep block decisions only for the critical lanes
- review low-coverage/high-failure modules and schedule new tests

## Recommendation

The right use of `LiminalQAengineer` in this repository is:

- not "a tool for writing tests"
- not "a replacement for coverage"
- but "the memory, triage, and merge-policy layer above the existing test pyramid"

If you want, the next practical step is to implement Phase 1 directly in:

- `.github/workflows/mesh-tests.yml`
- `.github/workflows/web4_runtime_ci.yml`
- `.github/workflows/ci.yml`

with one shared LiminalQA integration pattern.

## Implemented Baseline

As of 2026-04-04, the repository has moved beyond passive observability and now includes:

- shared pytest + optional LiminalQA runner action
- shared artifact summary action
- shared quality gate action
- enforcing gates on:
  - `mesh-tests.yml`
  - `ci.yml`
  - `web4_runtime_ci.yml`

The live thresholds are documented in `docs/CI_QUALITY_GATES.md`.
