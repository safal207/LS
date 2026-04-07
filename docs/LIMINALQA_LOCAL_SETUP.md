# LiminalQA Local Setup

This repository integrates with `LiminalQAengineer`, but the service itself should run as a separate local stack.

## Recommended local layout

- current repository: `.../deck`
- LiminalQA repository: `.../LiminalQAengineer`
- local ingest URL: `http://localhost:8080`

That keeps the test target and the quality-memory service separate.

## One-time setup

1. Copy `.env.liminalqa.local.example` to `.env.liminalqa.local`.
2. Adjust `LIMINALQA_REPO_DIR` only if you want the repo somewhere other than `..\LiminalQAengineer`.
3. Start the stack:

```powershell
pwsh ./scripts/liminalqa-local-up.ps1
```

The script will:

- create `.env.liminalqa.local` if it does not exist
- clone `safal207/LiminalQAengineer` next to this repo when needed
- `git pull --ff-only` on later runs
- start this repo's wrapper compose: `deploy/liminalqa-local.compose.yml`
- wait for `GET /health`

The wrapper compose intentionally starts only the services needed for local ingest:

- PostgreSQL
- `liminalqa-ingest`

It does not start the Selenium demo grid, because that is not needed for this repository's CI-memory flow.
It also uses local patched SQL migrations from `deploy/liminalqa-migrations/`, because the current upstream MVP migrations still contain `timestamptz` range bugs.

## Daily commands

Health check:

```powershell
pwsh ./scripts/liminalqa-local-health.ps1
```

Local dashboard:

```powershell
python tools/liminalqa_local_dashboard.py
```

Then open:

```text
http://127.0.0.1:8090
```

The dashboard gives you:

- health check
- one-click smoke publish
- local `mesh-tests` lane run
- quality report generate/publish flow
- simple query preview
- council analytics from `artifacts/council-ledger/*.json`
- a demo council-ledger generator so the charts are explorable before real coordination cycles exist

Stop the stack:

```powershell
pwsh ./scripts/liminalqa-local-down.ps1
```

Reset the local database volume if bootstrap failed or you need a clean re-init:

```powershell
pwsh ./scripts/liminalqa-local-reset.ps1
```

## How it answers

There are three separate modes:

- `ingest`: this repo sends test and quality facts into LiminalQA
- `query`: the LiminalQA service can answer structured requests from its database
- `report`: the LiminalQA report generator can render HTML summaries for a run

In other words, `LiminalQA` is not a Python module inside this repo. It is a separate service that listens on `LIMINALQA_URL`.

## Important boundary

`http://localhost:8080` is only reachable from your machine.

That means:

- local scripts can talk to it
- a self-hosted GitHub runner on the same machine can talk to it
- GitHub-hosted runners cannot talk to your localhost

For GitHub-hosted Actions, `LIMINALQA_URL` must point to a remotely reachable deployment of `LiminalQAengineer`.

## Current repo wiring

This repository already does the following when `LIMINALQA_URL` is set:

- pytest lanes send session telemetry through `pytest-liminalqa`
- CI quality-gate snapshots are aggregated into `artifacts/quality-report.json`
- workflow-level quality snapshots are published to `POST /ingest/batch`

So the only missing piece for local use is the actual running LiminalQA stack.
