# Network Precision Contributor Call

Status: **public contributor protocol for independent model and runtime runs**.

LS now has a deterministic proxy for one practical question:

```text
How much precision did the cooperative network add over a single answer?
```

This document asks contributors to run the same probe on their own machines,
local models, hosted models, or manual-review routes, then report the result in
a small reproducible note.

Public collection issue:

- [Contributor call: test Network Precision Gain on your models](https://github.com/safal207/LS/issues/571)

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

## Easiest IDE Run

If you use VS Code or Cursor:

1. Open the LS repository folder.
2. Choose **Terminal -> Run Task...**.
3. Run **LS: Prepare Contributor Report**.
4. Paste `reports/network_precision_contributor_report.md` into the GitHub contributor issue.

If you use OpenCode:

1. Open the LS repository folder.
2. Use the repo `opencode.json`.
3. Run `/ls-precision-report your-github-handle`.
4. Paste `reports/network_precision_contributor_report.md` into the GitHub contributor issue.

## MCP Agent Run

If your IDE agent (OpenCode, Cursor Agent, Claude Desktop, Codex, Copilot) supports MCP:

1. Connect to the LS MCP server via stdio: `python -m ls.agent_shell.mcp_server`
2. Call `ls_prepare_contributor_report` with optional `{"runner": "your-handle"}`
3. The agent receives the full report payload and can format it directly into
   the contributor issue.

Individual probes are also available as MCP tools:
`ls_run_network_precision_probe`, `ls_run_model_roster_probe`,
and `ls_run_network_trajectory_probe`.

CLI equivalent:

```bash
python scripts/prepare_network_precision_contributor_report.py \
  --output reports/network_precision_contributor_report.md
```

More IDE options:

- [`IDE_TESTING_ENTRYPOINTS.md`](IDE_TESTING_ENTRYPOINTS.md)

Also useful:

```bash
python scripts/run_model_roster_depth_probe.py --json
python scripts/run_nash_route_stability_demo.py --json
```

If you have local or hosted actors configured, run the live roster probe too:

```bash
python scripts/run_model_roster_depth_probe.py --live --json --max-tokens 180
```

Also useful:

```bash
python scripts/run_network_trajectory_demo.py --json
python scripts/run_network_trajectory_demo.py --cycles 10 --json
python scripts/run_conductor_noise_robustness_demo.py --cycles 6 --seeds 12 --json
python scripts/run_live_model_pilot.py --json
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
scope_bridge_propagation: propagation_product value from the run
temporal_coherence: temporal_product value from the run
temporal_drift: drift between levels over time
temporal_cycle: cycle detection score
temporal_lag: propagation lag between levels
temporal_resonance: cross-level resonance score
trajectory_cycles: number of cycles run
observer_delta_final: precision gain added by observer vs no-observer trajectory
observer_velocity_multiplier: how many times faster the network grows with observer
trajectory_gain_over_baseline: full trajectory end vs single baseline
precision_velocity: score change per cycle
conductor_noise_pass_rate: pass rate for noisy fresh/stale/no-reason/inverted ordering
conductor_noise_margin: fresh-minus-stale margin under moderate noise
live_model_pilot_decision: sample_pipeline_ready / live_route_captured / live_route_needs_review
live_model_pilot_score: pilot precision proxy from the live/sample route event
route_memory_key: route key from Route Memory v0 (if persisted)
route_memory_persisted: boolean, whether the route was saved to durable state
route_memory_health: validated_candidate / promising / needs_more_evidence / weak / untried
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
scope_bridge_propagation:
temporal_coherence:
temporal_drift:
temporal_cycle:
temporal_lag:
temporal_resonance:
trajectory_cycles:
observer_delta_final:
observer_velocity_multiplier:
trajectory_gain_over_baseline:
precision_velocity:
conductor_noise_pass_rate:
conductor_noise_margin:
live_model_pilot_decision:
live_model_pilot_score:
route_memory_key:
route_memory_persisted:
route_memory_health:
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
single baseline score:      0.1423
cooperative route score:    0.7436
full stack score:           0.8764

measured route reward gain: +0.6656
network precision gain:     +0.7341
stack added gain:           +0.1328
ratio vs baseline:          6.16x

scope bridge propagation:
  cooperative:              0.1364
  full stack:               0.5834

temporal coherence:
  cooperative:              0.0275 (drift=0.55, cycle=0.40, lag=0.50, resonance=0.25)
  full stack:               0.0720 (drift=0.15, cycle=0.75, lag=0.20, resonance=0.80)
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
