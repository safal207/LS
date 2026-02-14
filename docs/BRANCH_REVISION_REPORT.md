# Web4 Runtime — Branch Revision Report

Revision date: 2026-02-13

## Environment limitation

Only one local branch (`work`) is available in this clone, and no remote is configured. As a result, a full live scan of `main`, `codex/*`, `feature/*`, `plan/*`, `experiment/*` and old PR branches cannot be executed directly from refs.

To compensate, historical branch names were inferred from merge history (`git log --all`).

## Observable branches

| Branch | Status | Contains | Action |
|---|---|---|---|
| work | active | Integrated state after PR #110 (QoS, lifecycle, multi-transport, CI sync) | keep |

## Historical branches (inferred)

| Branch | Status | Contains | Action |
|---|---|---|---|
| codex/prepare-pr-plan-for-6.1 | merged | QoS, lifecycle hooks, multi-transport, 6.3.1 hotfix | can delete on remote if still present |
| codex/update-codex_tasks.md-status | merged | backlog/branch model updates | can delete on remote if still present |
| codex/add-api-parity-contract-tests | merged | Python↔Rust API parity tests | can delete on remote if still present |
| codex/add-health-metrics-to-rust_bridge.py | merged | bridge health metrics/fallback logging | can delete on remote if still present |
| codex/add-tests-for-pythonrust-bridge | merged | rust bridge tests | can delete on remote if still present |
| codex/expand-python-ci-in-workflow | merged | expanded CI checks | can delete on remote if still present |
| codex/create-formal-task-list-for-codex | merged | formalized task backlog | can delete on remote if still present |
| codex/fix-pyo3-ci-linking-issue | merged | PyO3 CI linking fixes | can delete on remote if still present |
| codex/analyze-current-state-of-main-branch | merged | status report generation | can delete on remote if still present |
| codex/create-new-pr-for-add-automatic-ruff-autofix-job | merged | ruff autofix workflow updates | can delete on remote if still present |
| codex/merge-ruff-autofix-workflow-into-main | merged | autofix workflow integration | can delete on remote if still present |
| codex/create-autonomous-execution-plan-for-codex | merged | runtime/mesh/platform execution plans | content archived in `docs/archive/` |

## Branches safe to delete (if they still exist remotely)

All merged historical `codex/*` branches listed above are candidates for deletion.

## Branches to keep

- `main` (canonical integration branch)
- `work` (active local working branch)
- any active, not-yet-merged `feature/*`, `plan/*`, `experiment/*` branches
