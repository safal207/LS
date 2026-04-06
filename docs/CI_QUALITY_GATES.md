# CI Quality Gates

## Purpose

This document records the active CI quality gates for the repository.

It complements:

- `docs/LIMINALQA_TEST_STRATEGY.md` for the long-term testing strategy
- `.github/actions/quality-gate/action.yml` for the reusable gate implementation
- `.github/workflows/*.yml` for the live enforcement points

## Current State

As of 2026-04-04, the repository has three active gate-enabled workflows:

| Workflow | Mode | Failure threshold | Line coverage threshold | Notes |
|---|---|---:|---:|---|
| `mesh-tests.yml` | enforcing | `0` | `30%` | first strict lane, calibrated from local mesh slice |
| `ci.yml` | enforcing | `0` | `12%` | wide module surface, lower baseline coverage |
| `web4_runtime_ci.yml` | enforcing | `0` | `25%` | threshold anchored by `hexagon-core` sub-slice |

## How A Gate Decides

The reusable gate reads JUnit XML and coverage XML from `artifacts/` and produces:

- `PASS`
- `WARN`
- `BLOCK`

It evaluates:

- whether JUnit artifacts exist
- whether coverage artifacts exist
- whether `failures + errors` exceed the configured maximum
- whether minimum line coverage stays above the configured threshold

When `enforce: "true"`, a `BLOCK` verdict fails the workflow step.

## Active Threshold Rationale

### 1. Mesh Tests

Workflow:

- `.github/workflows/mesh-tests.yml`

Current gate:

- `max-failures: 0`
- `min-line-coverage: 30`
- `enforce: true`

Calibration basis on 2026-04-04:

- local mesh slice passed with `19` tests
- observed line coverage was about `35.57%`

Reasoning:

- `30%` is strict enough to reject accidental coverage collapse
- it still leaves room for routine code movement without creating noisy failures

### 2. Security And CI Pipeline

Workflow:

- `.github/workflows/ci.yml`

Current gate:

- `max-failures: 0`
- `min-line-coverage: 12`
- `enforce: true`

Calibration basis on 2026-04-04:

- local test slice passed with `29` tests
- observed line coverage was about `13.44%`

Reasoning:

- this workflow spans a broad code surface through `--cov=agent --cov=codex --cov=python/modules`
- the broad denominator makes line coverage lower than lane-specific suites
- `12%` gives a real floor without turning the gate into random churn

### 3. Web4 Runtime CI

Workflow:

- `.github/workflows/web4_runtime_ci.yml`

Current gate:

- `max-failures: 0`
- `min-line-coverage: 25`
- `enforce: true`

Calibration basis on 2026-04-04:

- local Python slices passed:
  - `web4-runtime-smoke`: `44` tests
  - `web4-runtime-contract`: `86` tests
  - `hexagon-core`: `14` tests
- observed line coverage:
  - `52.80%`
  - `51.21%`
  - `25.39%`

Reasoning:

- `25%` is pegged to the lowest stable observed sub-slice
- this keeps the gate meaningful while avoiding false failures from the `hexagon-core` denominator

## Known Risk

The local Windows environment showed native access violations in:

- `python/tests/test_rust_bridge.py`
- `python/tests/test_api_parity.py`

This affects local calibration confidence for the Rust-backed portion of `web4_runtime_ci.yml`.

Important:

- the active gate still validates artifact presence, test failures, and coverage thresholds
- but Rust bridge instability should be tracked separately from gate mechanics
- if Linux CI stays stable while local Windows crashes continue, document that split explicitly rather than weakening the whole gate

## Operational Rules

When changing a threshold:

1. Run the matching lane locally or inspect recent CI artifact history.
2. Record the observed coverage and date.
3. Update this file together with the workflow.
4. Prefer small threshold moves.

Do not:

- raise thresholds without evidence
- lower thresholds to hide real regression
- mix environment instability with coverage policy

## Next Improvements

- Add PR comment or sticky check summary with gate verdicts.
- Feed LiminalQA verdicts into PR triage once enough run history exists.
- Split Rust-native instability policy from pure Python lane policy in `web4_runtime_ci.yml`.
