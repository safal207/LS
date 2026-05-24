# Network Precision Contributor Call

Status: **public contributor protocol for independent model and runtime runs**.

LS now has a deterministic proxy for one practical question:

```text
How much precision did the cooperative network add over a single answer?
```

This document asks contributors to run the same probe on their own machines,
local models, hosted models, or manual-review routes, then report the result in
a small reproducible note.

## Goal

Build a public contributor matrix for cooperative precision:

```text
same task
-> different model/runtime/environment
-> same visible metrics
-> better route memory
-> more precise network over time
```

This is not a model leaderboard. The goal is to learn which routes, evidence
gates, traces, and human boundaries make repeated AI co-work more precise.

## Minimum Run

From the repository root:

```bash
python scripts/run_network_precision_gain_demo.py
python scripts/run_network_precision_gain_demo.py --json
```

Also useful:

```bash
python scripts/run_model_roster_depth_probe.py --json
python scripts/run_nash_route_stability_demo.py --json
```

If you have local or hosted actors configured, run the live roster probe too:

```bash
python scripts/run_model_roster_depth_probe.py --live --json --max-tokens 180
```

## What To Report

Please report enough context for another contributor to understand the run.
Do not include secrets, private prompts, private customer data, API keys, tokens,
or proprietary code.

Recommended fields:

```text
runner_id: GitHub handle or pseudonym
run_date_utc: YYYY-MM-DD
os: Linux / macOS / Windows / WSL
python_version: e.g. 3.11.8
hardware: CPU / RAM / GPU or Apple Silicon notes
model_runtime: ollama / vllm / llama.cpp / API / manual / sample
models_tested: model names or "sample only"
ready_actors: actors that were available
unavailable_actors: actors that were not configured or failed
commands: exact commands used
network_precision_gain: value from the run
measured_route_reward_gain: value from the run
stack_added_gain_over_cooperation: value from the run
score_ratio_vs_baseline: value from the run
notes: anything surprising, slow, brittle, or useful
```

## Issue Comment Template

````md
### Environment

Runner:
Date:
OS:
Python:
Hardware:
Runtime:
Models:

### Commands

```bash
python scripts/run_network_precision_gain_demo.py --json
python scripts/run_model_roster_depth_probe.py --json
python scripts/run_nash_route_stability_demo.py --json
```

### Results

single_baseline_score:
cooperative_route_score:
full_stack_score:
measured_route_reward_gain:
network_precision_gain_over_baseline:
stack_added_gain_over_cooperation:
score_ratio_vs_baseline:
ready_actors:
unavailable_actors:

### Notes

Anything the run revealed about the model, runtime, hardware, route, or metric.
````

## What Good Runs Improve

Contributor runs help LS improve four things:

- **Route selection:** which cooperative path improves the task signal.
- **Evidence quality:** which gates and traces make a result reviewable.
- **Memory quality:** which successful routes should become reusable examples.
- **Boundary quality:** where the system should hold, ask, repair, or continue.

Over time, accepted runs can become curated fixtures:

```text
reports/trails/contributor/<runner_id>/<run_id>/network_precision.json
reports/trails/contributor/<runner_id>/<run_id>/environment.md
```

After review, safe examples may be promoted into:

```text
examples/network-precision/contributor-runs/<run_id>.json
examples/network-precision/contributor-runs/<run_id>.md
```

## Current Local Reference Result

The current deterministic reference run reports:

```text
single baseline score:      0.1603
cooperative route score:    0.7186
full stack score:           0.8628

measured route reward gain: +0.6656
network precision gain:     +0.7025
stack added gain:           +0.1442
ratio vs baseline:          5.3824x
```

Use this only as the current local reference. Independent contributor runs are
expected to show where the metric is stable, brittle, or incomplete.

## Boundary

Do not present this as:

- proof of formal Nash equilibrium;
- proof of global model superiority;
- proof that one model is generally better than another;
- proof of production safety;
- proof that LS makes models generally intelligent.

The narrow claim is:

```text
LS can measure whether a cooperative route plus evidence stack improves task
precision over a single-answer baseline on a visible, repeatable probe.
```

## Why This Matters

Most AI evaluation asks:

```text
Which model answered best?
```

LS asks a more operational question:

```text
Which cooperative route made the work more precise, and can that route be
remembered, reviewed, repeated, or improved?
```

That is the network we are inviting contributors to test.
