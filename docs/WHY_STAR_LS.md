# Why Star LS

LS is an early open-source project for **cooperative precision in AI co-work**.

It is a local-first evidence layer for asking:

```text
Which route of models, roles, evidence, and human review improved this task signal?
```

## Star this project if you care about

- AI agent oversight;
- reproducible AI evaluation artifacts;
- human-plus-model workflows;
- local-first AI infrastructure;
- code-review and PR-review agents;
- traceable cooperative reasoning;
- contributor-run checks across different models and hardware.

## The shortest useful demo

From the repository root:

```bash
python -m pip install jsonschema pytest
PYTHONPATH=.:python:python/modules python -m pytest python/tests/test_nash_route_stability.py
python scripts/run_nash_route_stability_demo.py --json
```

What this checks:

```text
schema
-> checked-in sample
-> negative fixtures
-> deterministic route-stability probe
-> regression test
-> explicit non-claims
```

## What makes this different

LS focuses on route evidence:

```text
task
-> route
-> role contributions
-> evidence
-> counterfactuals
-> repeatability decision
-> reviewer-visible artifact
```

## Current public contributor hook

The current public contributor hook is the route-stability matrix:

```text
run the same bounded probe across different OS, hardware, runtimes, fixtures, and model outputs
```

Start here:

- [`ROUTE_STABILITY_CONTRIBUTOR_RUNS.md`](ROUTE_STABILITY_CONTRIBUTOR_RUNS.md)
- [Issue #563: Contributor matrix](https://github.com/safal207/LS/issues/563)

## Good first contributions

- run the current probe on Linux CPU-only;
- run it on Windows / WSL;
- run it on Apple Silicon;
- add a sanitized role-output fixture from a local model;
- add a not-stable-yet fixture;
- add an unsupported-decision negative fixture;
- improve README navigation for new contributors.

## What not to claim

LS currently does **not** claim:

```text
formal Nash equilibrium;
global model ranking;
global contributor ranking;
statistical sufficiency;
production-grade governance;
that one route generalizes to all PR reviews.
```

The current claim is narrower:

```text
LS exposes a small, inspectable, regression-tested evidence path for cooperative AI route evaluation.
```

## One-line pitch

```text
LS helps AI teams measure which cooperative route improves task precision under a visible evidence chain.
```

If that direction matters to you, star the repo and try one contributor run.
