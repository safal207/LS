# Branching model

## Default branch

- The canonical default branch is `main`.
- CI workflows are bound to `main` for both `push` and `pull_request` events.

## Working process

1. Create short-lived feature branches from `main`.
2. Open Pull Requests targeting `main`.
3. Merge only after all required checks are green.

## CI scope

- `.github/workflows/web4_runtime_ci.yml` runs for changes targeting `main`.
- `.github/workflows/ruff_autofix.yml` runs on Python-related PRs targeting `main`.
