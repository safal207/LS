# Route Stability Sample Contract

Status: **working local research MVP contract**.

This document explains the reviewer-facing contract for LS Nash-style route
stability samples.

It is intentionally separate from the Cognitive Trail Run contract because a
route-stability sample answers a different question.

```text
Cognitive Trail Run
  -> Did a cooperative route improve one measured task signal over a baseline?

Route Stability Sample
  -> Does the full cooperative route still beat simple counterfactual routes?
```

## Contract Files

Schema:

```text
schemas/route_stability_sample.schema.json
```

Checked-in sample:

```text
examples/route-stability/nash_route_stability_sample.json
```

Deterministic demo generator:

```text
scripts/run_nash_route_stability_demo.py
```

Regression test:

```text
python/tests/test_nash_route_stability.py
```

CI workflow:

```text
.github/workflows/cognitive_trail_contract.yml
```

## What the Schema Guarantees

The JSON Schema checks the structural contract for a route-stability artifact.

It requires:

```text
demo
metric_version
trail_metric_version
interpretation_boundary
thresholds
full_route
baseline_route
counterfactuals
participant_marginal_contributions
stability
```

It also constrains key values:

```text
demo = ls_nash_route_stability
metric_version = nash_route_stability.v0.1
stability.decision in {stable_candidate, not_stable_yet}
route.kind in {full, baseline, ablation, deviation}
```

The schema makes sure the artifact has the right shape before a reviewer treats
it as a route-stability sample.

## What the Test Adds Beyond Schema

JSON Schema validates shape. The regression test validates the local deterministic
contract.

Run:

```bash
PYTHONPATH=.:python:python/modules python -m pytest python/tests/test_nash_route_stability.py
```

The test currently checks three things:

```text
1. The deterministic demo marks the full route as stable_candidate.
2. The checked-in sample matches schemas/route_stability_sample.schema.json.
3. The checked-in sample matches the demo --json output for stable core fields.
```

This means the sample is not only valid JSON. It is pinned to the current local
probe behavior.

## Current Expected Values

Current full cooperative route:

```text
pr_review>local>gonka>mimo
```

Current deterministic local result:

```text
full route reward:       0.7863
single baseline reward:  0.1207
coalition gain:          +0.6656
best counterfactual:     pr_review>local>gonka = 0.5613
stability margin:        +0.2250
decision:                stable_candidate
```

Participant marginal contributions:

```text
local: +0.3226
gonka: +0.2913
mimo:  +0.2250
```

## How to Validate Manually

Install dependencies:

```bash
python -m pip install jsonschema pytest
```

Validate the route-stability contract:

```bash
PYTHONPATH=.:python:python/modules python -m pytest python/tests/test_nash_route_stability.py
```

Generate the same payload manually:

```bash
python scripts/run_nash_route_stability_demo.py --json
```

Generate a reviewer artifact:

```bash
mkdir -p reports/trails/ci
python scripts/run_nash_route_stability_demo.py --json > reports/trails/ci/nash_route_stability.json
```

## CI Behavior

The Cognitive Trail Contract workflow runs the route-stability test and generates
a route-stability JSON artifact.

Workflow path:

```text
.github/workflows/cognitive_trail_contract.yml
```

The workflow is triggered by changes to:

```text
schemas/route_stability_sample.schema.json
examples/route-stability/*.json
scripts/run_nash_route_stability_demo.py
python/tests/test_nash_route_stability.py
```

Generated CI artifact path:

```text
reports/trails/ci/nash_route_stability.json
```

## Reviewer Interpretation

A valid stable-candidate route-stability sample means:

```text
For this deterministic local probe, the full cooperative route beat the configured single-route baseline, participant ablations, and bad-ordering counterfactual.
```

It does **not** mean:

```text
This is a formal Nash equilibrium proof.
This route is globally optimal.
These participants are globally best.
This result is statistically sufficient.
This route should be reused without human authority.
```

## Why This Contract Exists

Without a separate contract, the Nash-style sample would be only an informal JSON
example. This contract gives reviewers a small inspectable chain:

```text
schema
-> checked-in sample
-> deterministic generator
-> regression test
-> CI artifact
-> explicit non-claims
```

That is the minimum useful evidence boundary for this route-stability proxy.
