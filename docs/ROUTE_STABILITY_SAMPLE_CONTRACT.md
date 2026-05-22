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

Negative fixture:

```text
python/tests/fixtures/route-stability/invalid_metric_version.json
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
contract and its failure boundary.

Run:

```bash
PYTHONPATH=.:python:python/modules python -m pytest python/tests/test_nash_route_stability.py
```

The test currently checks four things:

```text
1. The deterministic demo marks the full route as stable_candidate.
2. The checked-in sample matches schemas/route_stability_sample.schema.json.
3. A broken fixture is rejected by the same schema.
4. The checked-in sample matches the demo --json output for stable core fields.
```

This means the sample is not only valid JSON. It is pinned to the current local
probe behavior, and the schema is tested against at least one known-bad artifact.

## Negative Fixture

The negative fixture lives outside `examples/route-stability/` on purpose:

```text
python/tests/fixtures/route-stability/invalid_metric_version.json
```

It should not be interpreted as a reviewer sample. It is a schema-failure fixture
for the test suite.

The fixture is intentionally invalid in two ways:

```text
metric_version = nash_route_stability.v999.0
unexpected_debug_field = schema must reject undeclared route-stability fields
```

The regression test expects the schema to reject both problems:

```text
wrong metric_version
unknown top-level field
```

This proves the route-stability schema is not only permissive documentation. It
actively blocks at least these classes of malformed artifacts before they can be
presented as valid route-stability evidence.

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

Validate the route-stability contract, checked-in sample, negative fixture, and deterministic output pin:

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
python/tests/fixtures/route-stability/*.json
scripts/run_nash_route_stability_demo.py
python/tests/test_nash_route_stability.py
docs/ROUTE_STABILITY_SAMPLE_CONTRACT.md
```

Generated CI artifact path:

```text
reports/trails/ci/nash_route_stability.json
```

## CI Evidence

The workflow summary exposes the route-stability evidence boundary directly in
GitHub Actions.

It should show that CI:

```text
1. tests the checked-in route-stability sample against schemas/route_stability_sample.schema.json;
2. confirms python/tests/fixtures/route-stability/invalid_metric_version.json is rejected;
3. pins the checked-in route-stability sample to scripts/run_nash_route_stability_demo.py --json;
4. generates reports/trails/ci/nash_route_stability.json as a reviewer artifact.
```

This makes the CI surface match the local evidence chain:

```text
schema
-> checked-in sample
-> negative fixture
-> deterministic generator
-> regression test
-> CI summary
-> CI artifact
```

CI visibility caveat:

```text
If GitHub API status endpoints return no workflow runs for a push commit, inspect the GitHub Actions UI directly. The contract still requires the workflow trigger paths and summary text above to remain in sync with the route-stability files.
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
-> negative fixture
-> deterministic generator
-> regression test
-> CI summary
-> CI artifact
-> explicit non-claims
```

That is the minimum useful evidence boundary for this route-stability proxy.
